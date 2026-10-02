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

})();
