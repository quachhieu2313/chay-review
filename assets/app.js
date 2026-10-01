/* Kim Chỉ Nam — script dùng chung cho mọi trang */
(function(){
  'use strict';

  // ---------- lưu trữ an toàn (trình duyệt chặn localStorage vẫn chạy được) ----------
  var store = {
    get: function(key, fallback){
      try{ var v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
      catch(e){ return fallback; }
    },
    set: function(key, value){
      try{ localStorage.setItem(key, JSON.stringify(value)); }catch(e){}
    }
  };

  var $ = function(sel, root){ return (root || document).querySelector(sel); };
  var $$ = function(sel, root){ return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function fmt(n, digits){
    return n.toLocaleString('vi-VN', {minimumFractionDigits:digits || 0, maximumFractionDigits:digits || 0});
  }
  function pad(n){ return (n < 10 ? '0' : '') + n; }
  function dateKey(d){ return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  // ---------- giao diện sáng / tối ----------
  var themeBtn = $('#themeToggle');
  if(themeBtn){
    themeBtn.addEventListener('click', function(){
      var root = document.documentElement;
      var current = root.getAttribute('data-theme') ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      store.set('kcn-theme', next);
    });
  }

  // ---------- menu điện thoại ----------
  var navToggle = $('#navToggle');
  var nav = $('nav.primary');
  if(navToggle && nav){
    navToggle.addEventListener('click', function(){
      var open = nav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(open));
    });
    $$('a', nav).forEach(function(a){
      a.addEventListener('click', function(){
        nav.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  // ---------- hiện dần khi cuộn ----------
  var reveals = $$('.reveal');
  if('IntersectionObserver' in window){
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){ e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, {rootMargin:'0px 0px -60px 0px'});
    reveals.forEach(function(el){ io.observe(el); });
  }else{
    reveals.forEach(function(el){ el.classList.add('in'); });
  }

  var yearEl = $('#year');
  if(yearEl) yearEl.textContent = new Date().getFullYear();

  // =====================================================================
  // BẢNG MỤC TIÊU HÔM NAY
  // =====================================================================
  var tracker = $('#tracker');
  if(tracker){
    var DAY_NAMES = ['CN','T2','T3','T4','T5','T6','T7'];
    var DAY_FULL = ['Chủ nhật','Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy'];
    var today = new Date();
    var todayKey = dateKey(today);

    var state = store.get('kcn-goals', null);
    if(!state || !Array.isArray(state.goals)){
      state = {
        day: todayKey,
        history: {},
        goals: [
          {id:1, text:'Đi bộ hoặc chạy 30 phút', cat:'Sức khỏe', done:false},
          {id:2, text:'Đọc 1 báo cáo tài chính quý', cat:'Tài chính', done:false},
          {id:3, text:'Hoàn thành việc quan trọng nhất trước 11 giờ', cat:'Công việc', done:false}
        ]
      };
    }
    // sang ngày mới: lưu kết quả hôm trước, bỏ đánh dấu
    if(state.day !== todayKey){
      var doneCount = state.goals.filter(function(g){ return g.done; }).length;
      state.history[state.day] = {done:doneCount, total:state.goals.length};
      state.goals.forEach(function(g){ g.done = false; });
      state.day = todayKey;
    }

    var listEl = $('#goalList');
    var barEl = $('#goalBar');
    var countEl = $('#goalCount');
    var pctEl = $('#goalPct');
    var streakEl = $('#streakDays');
    var weekEl = $('#week');

    $('#trackerDate').textContent = DAY_FULL[today.getDay()] + ', ' + today.getDate() + '/' + (today.getMonth() + 1) + '/' + today.getFullYear();

    function ratioFor(key){
      if(key === todayKey){
        var t = state.goals.length;
        return t ? state.goals.filter(function(g){ return g.done; }).length / t : 0;
      }
      var h = state.history[key];
      return h && h.total ? h.done / h.total : 0;
    }

    function streak(){
      var n = ratioFor(todayKey) > 0 ? 1 : 0;
      var d = new Date(today);
      for(var i = 0; i < 365; i++){
        d.setDate(d.getDate() - 1);
        if(ratioFor(dateKey(d)) > 0) n++; else break;
      }
      return n;
    }

    function save(){ store.set('kcn-goals', state); }

    function render(){
      var total = state.goals.length;
      var done = state.goals.filter(function(g){ return g.done; }).length;
      var pct = total ? Math.round(done / total * 100) : 0;

      if(!total){
        listEl.innerHTML = '<li class="goal-empty">Chưa có mục tiêu nào. Thêm một việc nhỏ bạn chắc chắn làm được hôm nay.</li>';
      }else{
        listEl.innerHTML = state.goals.map(function(g){
          return '<li class="goal' + (g.done ? ' done' : '') + '" data-id="' + g.id + '">' +
            '<button class="goal-check" type="button" aria-pressed="' + g.done + '" aria-label="Đánh dấu hoàn thành: ' + escapeHtml(g.text) + '">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2"><path d="M20 6L9 17l-5-5"/></svg></button>' +
            '<span class="goal-text">' + escapeHtml(g.text) + '</span>' +
            '<span class="tag">' + escapeHtml(g.cat) + '</span>' +
            '<button class="goal-del" type="button" aria-label="Xoá mục tiêu: ' + escapeHtml(g.text) + '">' +
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg></button>' +
          '</li>';
        }).join('');
      }

      barEl.style.width = pct + '%';
      countEl.textContent = done + '/' + total + ' mục tiêu';
      pctEl.textContent = pct + '%';
      streakEl.textContent = streak();

      // 7 ngày gần nhất
      var html = '';
      for(var i = 6; i >= 0; i--){
        var d = new Date(today); d.setDate(d.getDate() - i);
        var r = ratioFor(dateKey(d));
        var lvl = r >= 1 ? 'l3' : r >= 0.5 ? 'l2' : r > 0 ? 'l1' : '';
        html += '<div class="week-day' + (i === 0 ? ' today' : '') + '">' +
          '<div class="week-dot ' + lvl + '" title="' + d.getDate() + '/' + (d.getMonth() + 1) + ': ' + Math.round(r * 100) + '%"></div>' +
          '<span>' + DAY_NAMES[d.getDay()] + '</span></div>';
      }
      weekEl.innerHTML = html;
    }

    listEl.addEventListener('click', function(e){
      var li = e.target.closest('.goal'); if(!li) return;
      var id = Number(li.getAttribute('data-id'));
      if(e.target.closest('.goal-check')){
        state.goals.forEach(function(g){ if(g.id === id) g.done = !g.done; });
      }else if(e.target.closest('.goal-del')){
        state.goals = state.goals.filter(function(g){ return g.id !== id; });
      }else return;
      save(); render();
    });

    $('#goalForm').addEventListener('submit', function(e){
      e.preventDefault();
      var input = $('#goalInput');
      var text = input.value.trim();
      if(!text) return;
      var maxId = state.goals.reduce(function(m, g){ return Math.max(m, g.id); }, 0);
      state.goals.push({id:maxId + 1, text:text.slice(0, 120), cat:$('#goalCat').value, done:false});
      input.value = '';
      save(); render();
      listEl.scrollTop = listEl.scrollHeight;
    });

    save(); render();
  }

  // =====================================================================
  // MÁY TÍNH LÃI KÉP
  // =====================================================================
  var calc = $('#calc');
  if(calc){
    var inputs = {
      init: $('#cInit'), monthly: $('#cMonthly'), rate: $('#cRate'), years: $('#cYears')
    };

    function money(trieu){
      if(trieu >= 1000) return fmt(trieu / 1000, 2) + ' tỷ';
      return fmt(trieu, 0) + ' triệu';
    }

    function compute(){
      var init = Number(inputs.init.value);
      var monthly = Number(inputs.monthly.value);
      var rate = Number(inputs.rate.value) / 100 / 12;
      var years = Number(inputs.years.value);

      $('#oInit').textContent = fmt(init) + ' tr';
      $('#oMonthly').textContent = fmt(monthly, monthly % 1 ? 1 : 0) + ' tr';
      $('#oRate').textContent = fmt(Number(inputs.rate.value), 1) + '%';
      $('#oYears').textContent = years + ' năm';

      var value = init, paid = init, rows = [];
      for(var m = 1; m <= years * 12; m++){
        value = value * (1 + rate) + monthly;
        paid += monthly;
        if(m % 12 === 0) rows.push({paid:paid, value:value});
      }
      $('#rTotal').textContent = money(value);
      $('#rPaid').textContent = money(paid);
      $('#rGain').textContent = money(value - paid);

      // biểu đồ cột: phần gốc + phần lãi
      var svg = $('#barsSvg');
      var W = 600, H = 220, gap = rows.length > 25 ? 2 : 4;
      var bw = (W - gap * (rows.length - 1)) / rows.length;
      var max = rows.length ? rows[rows.length - 1].value : 1;
      var out = '';
      rows.forEach(function(r, i){
        var x = i * (bw + gap);
        var hv = r.value / max * H, hp = Math.min(r.paid, r.value) / max * H;
        out += '<rect x="' + x.toFixed(1) + '" y="' + (H - hv).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + (hv - hp).toFixed(1) + '" rx="2" fill="var(--accent)">' +
          '<title>Năm ' + (i + 1) + ': ' + money(r.value) + '</title></rect>' +
          '<rect x="' + x.toFixed(1) + '" y="' + (H - hp).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + hp.toFixed(1) + '" rx="2" fill="var(--ink-soft)" opacity=".35">' +
          '<title>Năm ' + (i + 1) + ': đã góp ' + money(r.paid) + '</title></rect>';
      });
      svg.innerHTML = out;
      $('#axisEnd').textContent = 'Năm ' + years;
      $('#axisMid').textContent = 'Năm ' + Math.max(1, Math.round(years / 2));
    }

    Object.keys(inputs).forEach(function(k){ inputs[k].addEventListener('input', compute); });
    compute();
  }

  // =====================================================================
  // THỊ TRƯỜNG (dữ liệu minh hoạ)
  // =====================================================================
  var lineChart = $('#lineChart');
  if(lineChart){
    // sinh số giả lập ổn định (giống nhau mỗi lần tải trang)
    function rng(seed){
      return function(){
        seed |= 0; seed = seed + 0x6D2B79F5 | 0;
        var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      };
    }
    function series(seed, last, vol, drift){
      var r = rng(seed), v = [1], i;
      for(i = 1; i < 250; i++) v.push(v[i - 1] * (1 + drift + (r() - 0.5) * vol));
      var k = last / v[v.length - 1];
      return v.map(function(x){ return x * k; });
    }
    // ngày giao dịch (bỏ thứ 7, CN), lùi từ ngày cuối
    var dates = [];
    (function(){
      var d = new Date(2026, 8, 30);
      while(dates.length < 250){
        if(d.getDay() !== 0 && d.getDay() !== 6) dates.unshift(new Date(d));
        d.setDate(d.getDate() - 1);
      }
    })();

    var INDICES = {
      VNINDEX: {label:'VN-INDEX', data:series(11, 1286.45, 0.022, 0.0006)},
      HNXINDEX: {label:'HNX-INDEX', data:series(29, 231.78, 0.026, 0.0002)},
      UPCOM: {label:'UPCOM-INDEX', data:series(47, 98.56, 0.016, 0.0003)}
    };
    var current = 'VNINDEX', range = 66;

    var path = $('#linePath'), area = $('#lineArea');
    var tip = $('#chartTip'), dot = $('#chartDot'), hline = $('#chartHline');
    var yLabels = $('#yLabels');
    var W = 1000, H = 260;

    function draw(){
      var data = INDICES[current].data.slice(-range);
      var ds = dates.slice(-range);
      var min = Math.min.apply(null, data), max = Math.max.apply(null, data);
      var margin = (max - min) * 0.1 || 1; min -= margin; max += margin;
      var pts = data.map(function(v, i){
        return [i / (data.length - 1) * (W - 60), H - (v - min) / (max - min) * H];
      });
      var d = 'M' + pts.map(function(p){ return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' L');
      path.setAttribute('d', d);
      area.setAttribute('d', d + ' L' + (W - 60) + ',' + H + ' L0,' + H + ' Z');

      var first = data[0], last = data[data.length - 1], chg = last - first, pct = chg / first * 100;
      var up = chg >= 0;
      path.setAttribute('stroke', up ? '#2FBF4F' : '#E8605E');
      $('#gradStop').setAttribute('stop-color', up ? '#2FBF4F' : '#E8605E');
      $('#chartName').textContent = INDICES[current].label;
      var c = $('#chartChg');
      c.className = up ? 'up' : 'down';
      c.textContent = (up ? '▲ +' : '▼ ') + fmt(pct, 2) + '% trong kỳ';

      var labels = '';
      for(var i = 4; i >= 0; i--) labels += '<span>' + fmt(min + (max - min) * i / 4, 0) + '</span>';
      yLabels.innerHTML = labels;

      lineChart.onmousemove = lineChart.ontouchmove = function(e){
        var rect = lineChart.getBoundingClientRect();
        var cx = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
        var plotW = rect.width * (W - 60) / W;
        var idx = Math.round(Math.max(0, Math.min(1, cx / plotW)) * (data.length - 1));
        var px = pts[idx][0] / W * rect.width, py = pts[idx][1] / H * rect.height;
        dot.style.display = tip.style.display = hline.style.display = 'block';
        dot.style.left = px + 'px'; dot.style.top = py + 'px';
        hline.style.left = px + 'px';
        var dd = ds[idx];
        tip.innerHTML = '<span>' + pad2(dd.getDate()) + '/' + pad2(dd.getMonth() + 1) + '/' + dd.getFullYear() + '</span>' + fmt(data[idx], 2);
        var tw = tip.offsetWidth;
        tip.style.left = Math.min(Math.max(0, px - tw / 2), rect.width - tw) + 'px';
      };
      lineChart.onmouseleave = function(){ dot.style.display = tip.style.display = hline.style.display = 'none'; };
    }
    function pad2(n){ return (n < 10 ? '0' : '') + n; }

    $$('.index-card').forEach(function(btn){
      btn.addEventListener('click', function(){
        current = btn.getAttribute('data-index');
        $$('.index-card').forEach(function(b){ b.setAttribute('aria-pressed', String(b === btn)); });
        draw();
      });
    });
    $$('.tabs button').forEach(function(btn){
      btn.addEventListener('click', function(){
        range = Number(btn.getAttribute('data-range'));
        $$('.tabs button').forEach(function(b){ b.setAttribute('aria-selected', String(b === btn)); });
        draw();
      });
    });
    draw();

    // ---------- bảng theo dõi cổ phiếu ----------
    var STOCKS = [
      {t:'FPT', n:'FPT Corp', p:128400, c:1.82, v:4.1},
      {t:'VCB', n:'Vietcombank', p:92800, c:0.43, v:2.3},
      {t:'HPG', n:'Hòa Phát', p:27650, c:-0.72, v:28.6},
      {t:'MWG', n:'Thế Giới Di Động', p:61300, c:2.15, v:6.8},
      {t:'VNM', n:'Vinamilk', p:63200, c:-0.31, v:3.2},
      {t:'TCB', n:'Techcombank', p:23450, c:1.30, v:12.4},
      {t:'MBB', n:'MB Bank', p:22150, c:0.23, v:15.9},
      {t:'VHM', n:'Vinhomes', p:41950, c:-1.29, v:5.5},
      {t:'GAS', n:'PV Gas', p:68900, c:0.58, v:1.1},
      {t:'SSI', n:'Chứng khoán SSI', p:26800, c:-0.93, v:18.2}
    ];
    STOCKS.forEach(function(s, i){
      var r = rng(100 + i), v = [0];
      for(var k = 1; k < 12; k++) v.push(v[k - 1] + (r() - 0.5) * 2);
      // lật đường nếu hướng cuối kỳ ngược với % thay đổi
      if((v[11] - v[0]) * s.c < 0) v = v.map(function(x){ return -x; });
      s.spark = v;
    });

    var sortKey = 't', sortDir = 1, filter = '';
    var body = $('#wlBody');

    function spark(vals, up){
      var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
      var pts = vals.map(function(v, i){
        return (i / (vals.length - 1) * 64).toFixed(1) + ',' + (22 - (v - mn) / ((mx - mn) || 1) * 20).toFixed(1);
      }).join(' ');
      return '<svg width="64" height="24" viewBox="0 0 64 24" aria-hidden="true"><polyline points="' + pts +
        '" fill="none" stroke="' + (up ? '#2FBF4F' : '#E8605E') + '" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }

    function renderTable(){
      var rows = STOCKS.filter(function(s){
        return !filter || s.t.indexOf(filter) > -1 || s.n.toUpperCase().indexOf(filter) > -1;
      }).sort(function(a, b){
        var x = a[sortKey], y = b[sortKey];
        return (x > y ? 1 : x < y ? -1 : 0) * sortDir;
      });
      if(!rows.length){
        body.innerHTML = '<div class="wl-empty">Không tìm thấy mã "' + escapeHtml(filter) + '" trong danh sách minh hoạ.</div>';
        return;
      }
      body.innerHTML = rows.map(function(s){
        var up = s.c >= 0;
        return '<div class="wl-row" role="row">' +
          '<span class="wl-ticker" role="cell">' + s.t + '</span>' +
          '<span class="wl-name" role="cell">' + s.n + '</span>' +
          '<span class="wl-num tabular" role="cell">' + fmt(s.p) + '</span>' +
          '<span class="wl-num tabular ' + (up ? 'up' : 'down') + '" role="cell">' + (up ? '+' : '') + fmt(s.c, 2) + '%</span>' +
          '<span class="wl-num tabular wl-vol" role="cell">' + fmt(s.v, 1) + ' tr</span>' +
          '<span class="wl-spark" role="cell">' + spark(s.spark, up) + '</span>' +
        '</div>';
      }).join('');
    }

    $$('.wl-head button').forEach(function(btn){
      btn.addEventListener('click', function(){
        var k = btn.getAttribute('data-sort');
        if(k === sortKey) sortDir = -sortDir; else { sortKey = k; sortDir = k === 't' || k === 'n' ? 1 : -1; }
        $$('.wl-head button').forEach(function(b){
          var arrow = b.querySelector('.arrow');
          arrow.textContent = b === btn ? (sortDir > 0 ? '↑' : '↓') : '';
          b.parentNode.setAttribute('aria-sort', b === btn ? (sortDir > 0 ? 'ascending' : 'descending') : 'none');
        });
        renderTable();
      });
    });

    var search = $('#siteSearch');
    if(search){
      search.addEventListener('input', function(){
        filter = search.value.trim().toUpperCase();
        renderTable();
      });
      search.addEventListener('keydown', function(e){
        if(e.key === 'Enter'){ document.getElementById('thi-truong').scrollIntoView(); }
      });
    }
    renderTable();
  }
})();
