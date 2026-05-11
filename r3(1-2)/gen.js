/**
 * Full Analysis Pipeline
 * ======================
 * Research Question: How do Chinese Diaspora scholars produce knowledge in higher education research?
 * Data source: 04_Diaspora_Articles_12195.xlsx (Chinese Diaspora article subset, n=12,195)
 * Classification based on: Authors, Diaspora_Author_Count, Addresses, Affiliations, Publication_Year
 * Outputs: Charts, tables, TSV files
 */

const XLSX = require('xlsx');
const { ChartJSNodeCanvas } = require('chartjs-node-canvas');
const { createCanvas } = require('canvas');
const fs = require('fs');
const ChartDataLabels = require('chartjs-plugin-datalabels');

// ============================================================
// 1. LOAD DATA
// ============================================================
const wb = XLSX.readFile('04_Diaspora_Articles_12195.xlsx');
const ws = wb.Sheets[wb.SheetNames[0]];
const data = XLSX.utils.sheet_to_json(ws);
console.log('Total articles loaded:', data.length);

// ============================================================
// 2. HELPER FUNCTIONS
// ============================================================
function countAuthors(authorsStr) {
  if (!authorsStr) return 0;
  return authorsStr.split(';').filter(a => a.trim()).length;
}

function hasMainlandChina(addr, aff) {
  const text = (addr || '') + ' ' + (aff || '');
  return /Peoples R China/i.test(text);
}

// ============================================================
// 3. CLASSIFICATION
// ============================================================
const soloArticles = [];
const collabHostArticles = [];
const collabHomelandArticles = [];
const collabDiasporaOnlyArticles = [];
const allCollaborative = [];

const yearTrend = {};

data.forEach((r, idx) => {
  const totalAuthors = countAuthors(r['Authors']);
  const diasporaCount = r['Diaspora_Author_Count'] || 0;
  const addr = r['Addresses'] || '';
  const aff = r['Affiliations'] || '';
  const mainland = hasMainlandChina(addr, aff);
  const nonDiaspora = totalAuthors > diasporaCount;
  const year = r['Publication Year'];

  const record = {
    index: idx,
    articleId: r['Article_ID_1based'],
    wosId: r['UT (Unique WOS ID)'],
    title: r['Article Title'],
    authors: r['Authors'],
    year: year,
    totalAuthors: totalAuthors,
    diasporaCount: diasporaCount,
    addresses: addr,
    affiliations: aff
  };

  if (totalAuthors === 1) {
    soloArticles.push(record);
  } else if (mainland) {
    collabHomelandArticles.push(record);
    allCollaborative.push({ ...record, collabType: 'with_motherland' });
  } else if (nonDiaspora) {
    collabHostArticles.push(record);
    allCollaborative.push({ ...record, collabType: 'with_host' });
  } else {
    collabDiasporaOnlyArticles.push(record);
    allCollaborative.push({ ...record, collabType: 'diaspora_only' });
  }

  if (year) {
    if (!yearTrend[year]) {
      yearTrend[year] = { solo: 0, collab: 0, diaspora_only: 0, with_host: 0, with_motherland: 0 };
    }
    if (totalAuthors === 1) yearTrend[year].solo++;
    else {
      yearTrend[year].collab++;
      if (mainland) yearTrend[year].with_motherland++;
      else if (nonDiaspora) yearTrend[year].with_host++;
      else yearTrend[year].diaspora_only++;
    }
  }
});

const totalSolo = soloArticles.length;
const totalCollab = allCollaborative.length;
const totalDiasporaOnly = collabDiasporaOnlyArticles.length;
const totalWithHost = collabHostArticles.length;
const totalWithMotherland = collabHomelandArticles.length;

console.log('\n=== CLASSIFICATION RESULTS ===');
console.log('Solo Work:', totalSolo, '(' + (totalSolo/data.length*100).toFixed(1) + '%)');
console.log('Collaborative Work:', totalCollab, '(' + (totalCollab/data.length*100).toFixed(1) + '%)');
console.log('  - Diaspora-Only:', totalDiasporaOnly, '(' + (totalDiasporaOnly/data.length*100).toFixed(1) + '%)');
console.log('  - With Host-Country:', totalWithHost, '(' + (totalWithHost/data.length*100).toFixed(1) + '%)');
console.log('  - With Homeland:', totalWithMotherland, '(' + (totalWithMotherland/data.length*100).toFixed(1) + '%)');

// ============================================================
// 4. SAVE CLASSIFIED TSV FILES
// ============================================================
function writeTSV(filename, records, headers, fields) {
  const lines = [headers.join('\t')];
  records.forEach(r => {
    lines.push(fields.map(f => String(r[f] || '')).join('\t'));
  });
  fs.writeFileSync(filename, lines.join('\n'), 'utf8');
  console.log('TSV saved:', filename, '(' + records.length + ' rows)');
}

writeTSV(
  'solo_work_articles.tsv',
  soloArticles,
  ['Article_ID', 'WOS_ID', 'Year', 'Title', 'Authors', 'Total_Authors'],
  ['articleId', 'wosId', 'year', 'title', 'authors', 'totalAuthors']
);

writeTSV(
  'collaborative_articles.tsv',
  allCollaborative,
  ['Article_ID', 'WOS_ID', 'Year', 'Title', 'Authors', 'Total_Authors', 'Diaspora_Count', 'Collab_Type', 'Addresses', 'Affiliations'],
  ['articleId', 'wosId', 'year', 'title', 'authors', 'totalAuthors', 'diasporaCount', 'collabType', 'addresses', 'affiliations']
);

writeTSV(
  'host_country_collaboration.tsv',
  collabHostArticles,
  ['Article_ID', 'WOS_ID', 'Year', 'Title', 'Authors', 'Addresses', 'Affiliations'],
  ['articleId', 'wosId', 'year', 'title', 'authors', 'addresses', 'affiliations']
);

writeTSV(
  'homeland_collaboration.tsv',
  collabHomelandArticles,
  ['Article_ID', 'WOS_ID', 'Year', 'Title', 'Authors', 'Addresses', 'Affiliations'],
  ['articleId', 'wosId', 'year', 'title', 'authors', 'addresses', 'affiliations']
);

writeTSV(
  'diaspora_only_collaboration.tsv',
  collabDiasporaOnlyArticles,
  ['Article_ID', 'WOS_ID', 'Year', 'Title', 'Authors', 'Addresses', 'Affiliations'],
  ['articleId', 'wosId', 'year', 'title', 'authors', 'addresses', 'affiliations']
);

// ============================================================
// 5. CHART GENERATION SETUP
// ============================================================
const years = Object.keys(yearTrend).sort((a,b) => parseInt(a) - parseInt(b));

const chartJSNodeCanvas = new ChartJSNodeCanvas({
  width: 1100, height: 700, backgroundColour: '#ffffff',
  chartCallback: (ChartJS) => {
    ChartJS.defaults.font.family = 'Arial, sans-serif';
    ChartJS.register(ChartDataLabels);
  }
});

// ============================================================
// 6. CHART 1: Solo vs Collaboration (with data labels)
// ============================================================
(async () => {
  const pie1 = {
    type: 'doughnut',
    data: {
      labels: ['Solo Work', 'Collaborative Work'],
      datasets: [{
        data: [totalSolo, totalCollab],
        backgroundColor: ['#FF6B6B', '#4ECDC4'],
        borderWidth: 3, borderColor: '#fff', hoverOffset: 10
      }]
    },
    options: {
      responsive: false, layout: { padding: 40 },
      plugins: {
        title: { display: true, text: 'Solo Work vs. Collaboration (n = 12,195)', font: { size: 22, weight: 'bold' }, padding: { top: 10, bottom: 20 } },
        legend: { position: 'bottom', labels: { font: { size: 16 }, padding: 20 } },
        datalabels: {
          color: '#fff', font: { size: 20, weight: 'bold' },
          formatter: (value, ctx) => {
            const total = ctx.dataset.data.reduce((a,b)=>a+b,0);
            const pct = (value/total*100).toFixed(1);
            return value.toLocaleString() + '\n(' + pct + '%)';
          }
        }
      }
    }
  };
  fs.writeFileSync('final_chart_1.png', await chartJSNodeCanvas.renderToBuffer(pie1));
  console.log('Chart 1 saved: final_chart_1.png');

  // ============================================================
  // 7. CHART 2: Collaboration Partners (with data labels)
  // ============================================================
  const pie2 = {
    type: 'doughnut',
    data: {
      labels: ['Diaspora-Only', 'With Host-Country Scholars', 'With Homeland Scholars'],
      datasets: [{
        data: [totalDiasporaOnly, totalWithHost, totalWithMotherland],
        backgroundColor: ['#FFD93D', '#45B7D1', '#96CEB4'],
        borderWidth: 3, borderColor: '#fff', hoverOffset: 10
      }]
    },
    options: {
      responsive: false, layout: { padding: 40 },
      plugins: {
        title: { display: true, text: 'Collaboration Partners (n = 11,014)', font: { size: 21, weight: 'bold' }, padding: { top: 10, bottom: 20 } },
        legend: { position: 'bottom', labels: { font: { size: 15 }, padding: 15 } },
        datalabels: {
          color: '#333', font: { size: 17, weight: 'bold' },
          formatter: (value, ctx) => {
            const total = ctx.dataset.data.reduce((a,b)=>a+b,0);
            const pct = (value/total*100).toFixed(1);
            return value.toLocaleString() + '\n(' + pct + '%)';
          }
        }
      }
    }
  };
  fs.writeFileSync('final_chart_2.png', await chartJSNodeCanvas.renderToBuffer(pie2));
  console.log('Chart 2 saved: final_chart_2.png');

  // ============================================================
  // 8. CHART 3: Trend - Solo vs Collaboration (with data labels)
  // ============================================================
  const line1 = {
    type: 'line',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Solo Work',
          data: years.map(y => yearTrend[y].solo),
          borderColor: '#FF6B6B',
          backgroundColor: 'rgba(255,107,107,0.08)',
          borderWidth: 2.5,
          pointRadius: 5,
          pointBackgroundColor: '#FF6B6B',
          fill: true,
          tension: 0.3
        },
        {
          label: 'Collaborative Work',
          data: years.map(y => yearTrend[y].collab),
          borderColor: '#4ECDC4',
          backgroundColor: 'rgba(78,205,196,0.08)',
          borderWidth: 2.5,
          pointRadius: 5,
          pointBackgroundColor: '#4ECDC4',
          fill: true,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: false,
      plugins: {
        title: { display: true, text: 'Trend of Solo Work vs. Collaboration (1991-2024)', font: { size: 20, weight: 'bold' }, padding: { top: 10, bottom: 20 } },
        legend: { position: 'bottom', labels: { font: { size: 16 }, padding: 20 } },
        datalabels: {
          align: 'top',
          offset: 4,
          color: (ctx) => ctx.dataset.borderColor,
          font: { size: 10, weight: 'bold' },
          formatter: (value) => value > 0 ? value : ''
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Publication Year', font: { size: 15 } },
          grid: { display: false },
          ticks: { font: { size: 11 }, maxRotation: 45 }
        },
        y: {
          title: { display: true, text: 'Number of Articles', font: { size: 15 } },
          grid: { color: '#f0f0f0' }
        }
      }
    }
  };
  fs.writeFileSync('final_chart_3_with_labels.png', await chartJSNodeCanvas.renderToBuffer(line1));
  console.log('Chart 3 saved: final_chart_3_with_labels.png');

  // ============================================================
  // 9. CHART 4: Trend - Collaboration Partners (%) (with data labels)
  // ============================================================
  const pctData = years.map(y => {
    const d = yearTrend[y];
    const total = d.diaspora_only + d.with_host + d.with_motherland;
    return {
      diaspora: total > 0 ? (d.diaspora_only / total * 100) : 0,
      host: total > 0 ? (d.with_host / total * 100) : 0,
      motherland: total > 0 ? (d.with_motherland / total * 100) : 0
    };
  });

  const bar1 = {
    type: 'bar',
    data: {
      labels: years,
      datasets: [
        {
          label: 'Diaspora-Only',
          data: pctData.map(d => d.diaspora),
          backgroundColor: '#FFD93D',
          borderWidth: 0
        },
        {
          label: 'With Host-Country',
          data: pctData.map(d => d.host),
          backgroundColor: '#45B7D1',
          borderWidth: 0
        },
        {
          label: 'With Homeland',
          data: pctData.map(d => d.motherland),
          backgroundColor: '#96CEB4',
          borderWidth: 0
        }
      ]
    },
    options: {
      responsive: false,
      plugins: {
        title: { display: true, text: 'Changing Patterns of Collaboration Partners (%)', font: { size: 20, weight: 'bold' }, padding: { top: 10, bottom: 20 } },
        legend: { position: 'bottom', labels: { font: { size: 14 }, padding: 12 } },
        datalabels: {
          color: '#333',
          font: { size: 9, weight: 'bold' },
          formatter: (value) => value >= 3 ? value.toFixed(0) + '%' : '',
          display: (ctx) => ctx.dataset.data[ctx.dataIndex] >= 3
        }
      },
      scales: {
        x: {
          stacked: true,
          title: { display: true, text: 'Publication Year', font: { size: 15 } },
          grid: { display: false },
          ticks: { font: { size: 11 }, maxRotation: 45 }
        },
        y: {
          stacked: true,
          max: 100,
          title: { display: true, text: 'Percentage (%)', font: { size: 15 } },
          grid: { color: '#f0f0f0' }
        }
      }
    }
  };
  fs.writeFileSync('final_chart_4_with_labels.png', await chartJSNodeCanvas.renderToBuffer(bar1));
  console.log('Chart 4 saved: final_chart_4_with_labels.png');

  // ============================================================
  // 10. TABLE IMAGES (using canvas)
  // ============================================================
  function drawTable(filename, title, headers, rows, colWidths) {
    const padX = 60;
    const tableW = colWidths.reduce((a,b)=>a+b,0);
    const canvasW = Math.max(1300, tableW + padX*2);
    const canvas = createCanvas(canvasW, 150 + rows.length * 55);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0,0,canvas.width,canvas.height);
    const startX = (canvasW - tableW) / 2;
    const startY = 90;
    const rowH = 55;
    ctx.fillStyle = '#333'; ctx.font = 'bold 24px Arial'; ctx.textAlign = 'center';
    ctx.fillText(title, canvas.width/2, 50);
    ctx.fillStyle = '#4ECDC4'; ctx.fillRect(startX, startY, tableW, rowH);
    ctx.fillStyle = '#fff'; ctx.font = 'bold 17px Arial'; ctx.textAlign = 'left';
    let x = startX + 20;
    headers.forEach((h,i)=>{ ctx.fillText(h, x, startY+35); x+=colWidths[i]; });
    rows.forEach((row,ri)=>{
      const y = startY + rowH*(ri+1);
      ctx.fillStyle = ri%2===0 ? '#f8f9fa' : '#fff';
      ctx.fillRect(startX, y, tableW, rowH);
      ctx.strokeStyle='#e0e0e0'; ctx.lineWidth=1; ctx.strokeRect(startX,y,tableW,rowH);
      ctx.fillStyle='#333'; ctx.font='16px Arial'; x=startX+20;
      row.forEach((cell,ci)=>{ ctx.fillText(String(cell), x, y+35); x+=colWidths[ci]; });
    });
    ctx.strokeStyle='#333'; ctx.lineWidth=2; ctx.strokeRect(startX,startY,tableW,rowH*(rows.length+1));
    fs.writeFileSync(filename, canvas.toBuffer('image/png'));
    console.log('Table saved:', filename);
  }

  drawTable(
    'final_table_1.png',
    'Table 1. Overall Pattern (n = 12,195)',
    ['Category','Count','% of Total','% within Collaborative'],
    [
      ['Solo Work','1,181','9.7%','-'],
      ['Collaborative Work','11,014','90.3%','100.0%'],
      ['  Diaspora-Only','356','2.9%','3.2%'],
      ['  With Host-Country','9,616','78.8%','87.3%'],
      ['  With Homeland','1,042','8.5%','9.5%']
    ],
    [420,160,220,300]
  );

  const selYears = [1991,1995,2000,2005,2010,2015,2020,2024];
  const rows2 = selYears.map(y=>{
    const d=yearTrend[y]; if(!d) return [String(y),'-','-','-','-','-'];
    const total=d.solo+d.collab;
    return [String(y),total.toLocaleString(),d.solo.toLocaleString(),d.collab.toLocaleString(),d.with_motherland.toLocaleString(),total>0?((d.with_motherland/total*100).toFixed(1)+'%'):'-'];
  });
  drawTable(
    'final_table_2.png',
    'Table 2. Yearly Trend (Selected Years)',
    ['Year','Total','Solo','Collaborative','With Homeland','Homeland % of Total'],
    rows2, [110,140,140,180,200,200]
  );

  drawTable(
    'final_table_3.png',
    'Table 3. Collaborative Articles by Partner (n = 11,014)',
    ['Collaboration Type','Count','% of All','% of Collaborative'],
    [
      ['Diaspora-Only','356','2.9%','3.2%'],
      ['With Host-Country Scholars','9,616','78.8%','87.3%'],
      ['With Homeland (China) Scholars','1,042','8.5%','9.5%']
    ],
    [460,160,220,300]
  );

  console.log('\n=== ALL OUTPUTS COMPLETE ===');
})();
