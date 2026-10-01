/* Kim Chỉ Nam — các trang dùng dữ liệu thật: Thị trường, ETF, chi tiết ETF, Quỹ mô phỏng, trang chủ */
(function(){
  'use strict';

  var BASE = window.KCN_BASE || '';
  var $ = function(s, r){ return (r || document).querySelector(s); };
  var $$ = function(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  // ---------------------------------------------------------------- tiện ích
  function fmt(n, d){
    if(n === null || n === undefined || isNaN(n)) return '–';
    return Number(n).toLocaleString('vi-VN', {minimumFractionDigits:d || 0, maximumFractionDigits:d || 0});
  }
  function pct(n, d){
    if(n === null || n === undefined || isNaN(n)) return '–';
    return (n > 0 ? '+' : n < 0 ? '−' : '') + fmt(Math.abs(n), d === undefined ? 2 : d) + '%';
  }
  function moc(ngay, luc){ return ngayVN(ngay) + (luc ? ' lúc ' + luc : ''); }
  function cls(n){ return n > 0 ? 'up' : n < 0 ? 'down' : ''; }
  function ngayVN(s){ if(!s) return '–'; var p = s.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }
  function tien(dong){
    if(dong === null || dong === undefined) return '–';
    if(Math.abs(dong) >= 1e9) return fmt(dong / 1e9, 2) + ' tỷ';
    if(Math.abs(dong) >= 1e6) return fmt(dong / 1e6, 1) + ' triệu';
    return fmt(dong) + ' đ';
  }
  function esc(s){
    return String(s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; });
  }
  function css(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  var cache = {};
  function load(path){
    if(!cache[path]){
      cache[path] = fetch(BASE + '/assets/data/' + path, {cache:'no-cache'}).then(function(r){
        if(!r.ok) throw new Error(path + ' ' + r.status);
        return r.json();
      });
    }
    return cache[path];
  }
  function fail(el, msg){
    if(el) el.innerHTML = '<div class="empty-state">' + (msg || 'Chưa tải được dữ liệu. Vui lòng thử lại sau.') + '</div>';
  }

  // lợi nhuận theo kỳ (giống cách tính trong script Python)
  function returns(d, c){
    var n = c.length, last = c[n - 1];
    function back(k){ return n > k ? (last / c[n - 1 - k] - 1) * 100 : null; }
    var y = d[n - 1].slice(0, 4), ytd = null;
    for(var i = n - 1; i >= 0; i--){ if(d[i].slice(0, 4) < y){ ytd = (last / c[i] - 1) * 100; break; } }
    return {'1d':back(1), '1m':back(21), '3m':back(63), '6m':back(126), 'ytd':ytd, '1y':back(252), '3y':back(756)};
  }
  function sparkSvg(vals, w, h, color){
    if(!vals || vals.length < 2) return '';
    var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
    var pts = vals.map(function(v, i){
      return (i / (vals.length - 1) * w).toFixed(1) + ',' + (h - 2 - (v - mn) / ((mx - mn) || 1) * (h - 4)).toFixed(1);
    }).join(' ');
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="none" aria-hidden="true"><polyline points="' + pts +
      '" fill="none" stroke="' + color + '" stroke-width="1.7" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }

  // ---------------------------------------------------------------- biểu đồ đường nhiều chuỗi
  // series: [{name, color, d:[ngày], c:[giá]}] ; chuỗi đầu tiên quyết định trục thời gian
  function LineChart(el, opts){
    opts = opts || {};
    el.classList.add('lc');
    el.innerHTML =
      '<div class="lc-plot"><svg viewBox="0 0 1000 300" preserveAspectRatio="none" role="img" aria-label="' + esc(opts.label || 'Biểu đồ') + '"></svg>' +
      '<div class="lc-y"></div><div class="lc-vline"></div><div class="lc-dots"></div><div class="lc-tip"></div></div>' +
      '<div class="lc-x"></div><div class="lc-legend"></div>';
    var svg = $('svg', el), plot = $('.lc-plot', el), yBox = $('.lc-y', el), xBox = $('.lc-x', el);
    var vline = $('.lc-vline', el), dots = $('.lc-dots', el), tip = $('.lc-tip', el), legend = $('.lc-legend', el);
    var W = 1000, H = 300, PW = 930; // chừa lề phải cho nhãn trục Y
    var state = null;

    function render(series, months, normalize){
      series = series.filter(function(s){ return s && s.d && s.d.length > 1; });
      if(!series.length){ svg.innerHTML = ''; return; }
      var main = series[0];
      var start = 0;
      if(months){
        var end = new Date(main.d[main.d.length - 1]);
        end.setMonth(end.getMonth() - months);
        var iso = end.toISOString().slice(0, 10);
        while(start < main.d.length - 2 && main.d[start] < iso) start++;
      }
      var dates = main.d.slice(start);
      // gióng các chuỗi khác theo ngày của chuỗi chính (lấy giá gần nhất trước đó)
      var lines = series.map(function(s){
        var map = {}, out = [], j = 0, last = null;
        for(var k = 0; k < s.d.length; k++) map[s.d[k]] = s.c[k];
        // giá gần nhất trước ngày bắt đầu
        while(j < s.d.length && s.d[j] <= dates[0]){ last = s.c[j]; j++; }
        dates.forEach(function(dt){
          if(map[dt] !== undefined) last = map[dt];
          out.push(last);
        });
        var base = null;
        for(var q = 0; q < out.length; q++){ if(out[q] !== null){ base = out[q]; break; } }
        if(normalize) out = out.map(function(v){ return v === null || base === null ? null : v / base * 100; });
        return {name:s.name, color:s.color, v:out, raw:s};
      });
      var all = [];
      lines.forEach(function(l){ l.v.forEach(function(v){ if(v !== null) all.push(v); }); });
      var mn = Math.min.apply(null, all), mx = Math.max.apply(null, all);
      var pad = (mx - mn) * 0.08 || 1; mn -= pad; mx += pad;
      if(opts.minZero && mn < 0) mn = 0;
      function X(i){ return dates.length < 2 ? 0 : i / (dates.length - 1) * PW; }
      function Y(v){ return H - (v - mn) / (mx - mn) * H; }

      var html = '';
      for(var g = 0; g <= 4; g++){
        var gy = (g / 4 * H).toFixed(1);
        html += '<line x1="0" x2="' + PW + '" y1="' + gy + '" y2="' + gy + '" stroke="var(--grid)" vector-effect="non-scaling-stroke"/>';
      }
      if(normalize){
        html += '<line x1="0" x2="' + PW + '" y1="' + Y(100).toFixed(1) + '" y2="' + Y(100).toFixed(1) + '" stroke="var(--muted)" stroke-dasharray="4 4" vector-effect="non-scaling-stroke" opacity=".6"/>';
      }
      lines.slice().reverse().forEach(function(l, idx){
        var d = '', pen = false;
        l.v.forEach(function(v, i){
          if(v === null){ pen = false; return; }
          d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1);
          pen = true;
        });
        var isMain = idx === lines.length - 1;
        if(isMain && opts.area){
          html += '<path d="' + d + 'L' + X(l.v.length - 1).toFixed(1) + ',' + H + 'L0,' + H + 'Z" fill="' + l.color + '" opacity=".09"/>';
        }
        html += '<path d="' + d + '" fill="none" stroke="' + l.color + '" stroke-width="' + (isMain ? 2.4 : 1.8) +
          '" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>';
      });
      svg.innerHTML = html;

      var yl = '';
      for(var t = 4; t >= 0; t--){
        var val = mn + (mx - mn) * t / 4;
        yl += '<span>' + (normalize ? pct(val - 100, 0) : opts.yFmt ? opts.yFmt(val) : fmt(val, opts.yDigits || 0)) + '</span>';
      }
      yBox.innerHTML = yl;
      var xl = '';
      [0, 0.33, 0.66, 1].forEach(function(f){ xl += '<span>' + ngayVN(dates[Math.round(f * (dates.length - 1))]) + '</span>'; });
      xBox.innerHTML = xl;

      legend.innerHTML = lines.map(function(l){
        var first = null, last = null;
        l.v.forEach(function(v){ if(v !== null){ if(first === null) first = v; last = v; } });
        var ch = first ? (last / first - 1) * 100 : null;
        if(opts.noChange) return '<span><i style="background:' + l.color + '"></i>' + esc(l.name) + '</span>';
        return '<span><i style="background:' + l.color + '"></i>' + esc(l.name) + ' <b class="' + cls(ch) + '">' + pct(ch) + '</b></span>';
      }).join('');

      state = {dates:dates, lines:lines, X:X, Y:Y, normalize:normalize};
    }

    function move(clientX){
      if(!state) return;
      var rect = plot.getBoundingClientRect();
      var f = Math.max(0, Math.min(1, (clientX - rect.left) / (rect.width * PW / W)));
      var i = Math.round(f * (state.dates.length - 1));
      var px = state.X(i) / W * rect.width;
      vline.style.display = tip.style.display = 'block';
      vline.style.left = px + 'px';
      var dh = '', th = '<b>' + ngayVN(state.dates[i]) + '</b>';
      state.lines.forEach(function(l){
        var v = l.v[i];
        if(v === null) return;
        dh += '<i style="left:' + px + 'px;top:' + (state.Y(v) / H * rect.height) + 'px;background:' + l.color + '"></i>';
        var shown = state.normalize ? pct(v - 100) : opts.yFmt ? opts.yFmt(v) : fmt(v, opts.yDigits || 0);
        th += '<span><em style="background:' + l.color + '"></em>' + esc(l.name) + ': ' + shown + '</span>';
      });
      dots.innerHTML = dh;
      tip.innerHTML = th;
      var tw = tip.offsetWidth;
      tip.style.left = (px + 14 + tw > rect.width ? px - tw - 14 : px + 14) + 'px';
    }
    function hide(){ vline.style.display = tip.style.display = 'none'; dots.innerHTML = ''; }
    plot.addEventListener('mousemove', function(e){ move(e.clientX); });
    plot.addEventListener('touchmove', function(e){ move(e.touches[0].clientX); }, {passive:true});
    plot.addEventListener('mouseleave', hide);
    plot.addEventListener('touchend', hide);

    return {render:render};
  }

  // nút chọn khoảng thời gian: <div class="seg" data-target="..."><button data-m="12">
  function bindRange(box, initial, cb){
    var btns = $$('button', box);
    btns.forEach(function(b){
      b.setAttribute('aria-pressed', String(b.getAttribute('data-m') === String(initial)));
      b.addEventListener('click', function(){
        btns.forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
        cb(Number(b.getAttribute('data-m')) || 0);
      });
    });
  }

  function palette(){
    return [css('--s1'), css('--s2'), css('--s3'), css('--s4')];
  }

  // bảng lợi nhuận theo kỳ
  var KY = [['1m','1 tháng'], ['3m','3 tháng'], ['6m','6 tháng'], ['ytd','Từ đầu năm'], ['1y','1 năm'], ['3y','3 năm']];
  function returnsTable(el, rows){
    var h = '<table class="ret-table"><thead><tr><th scope="col"></th>' +
      KY.map(function(k){ return '<th scope="col">' + k[1] + '</th>'; }).join('') + '</tr></thead><tbody>';
    rows.forEach(function(r){
      h += '<tr' + (r.muted ? ' class="muted-row"' : '') + '><th scope="row">' + (r.color ? '<i style="background:' + r.color + '"></i>' : '') + esc(r.name) + '</th>' +
        KY.map(function(k){ var v = r.ret[k[0]]; return '<td class="' + (r.muted ? '' : cls(v)) + '">' + pct(v) + '</td>'; }).join('') + '</tr>';
    });
    el.innerHTML = h + '</tbody></table>';
  }

  // =====================================================================
  // POPUP CHI TIẾT MÃ CỔ PHIẾU (biểu đồ nến TradingView Lightweight Charts v5)
  // =====================================================================
  var LWC_URL = 'https://cdn.jsdelivr.net/npm/lightweight-charts@5.2.1/dist/lightweight-charts.standalone.production.js';
  var lwcPromise = null;
  function loadLwc(){
    if(window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
    if(!lwcPromise){
      lwcPromise = new Promise(function(ok, no){
        var s = document.createElement('script');
        s.src = LWC_URL; s.async = true;
        s.onload = function(){ ok(window.LightweightCharts); };
        s.onerror = function(){ lwcPromise = null; no(new Error('Không tải được thư viện biểu đồ')); };
        document.head.appendChild(s);
      });
    }
    return lwcPromise;
  }

  // ---------- công thức chỉ báo kỹ thuật (mảng trả về cùng độ dài, chỗ chưa đủ dữ liệu là null)
  var TA = {
    sma: function(a, n){
      var out = [], sum = 0;
      for(var i = 0; i < a.length; i++){
        sum += a[i];
        if(i >= n) sum -= a[i - n];
        out.push(i >= n - 1 ? sum / n : null);
      }
      return out;
    },
    ema: function(a, n){
      var out = [], k = 2 / (n + 1), prev = null, sum = 0, cnt = 0;
      for(var i = 0; i < a.length; i++){
        var v = a[i];
        if(v === null){ out.push(null); continue; }
        if(prev === null){
          sum += v; cnt++;
          if(cnt === n){ prev = sum / n; out.push(prev); } else out.push(null);
        }else{ prev = v * k + prev * (1 - k); out.push(prev); }
      }
      return out;
    },
    bb: function(c, n, m){
      var mid = TA.sma(c, n), up = [], lo = [];
      for(var i = 0; i < c.length; i++){
        if(mid[i] === null){ up.push(null); lo.push(null); continue; }
        var s = 0;
        for(var j = i - n + 1; j <= i; j++) s += (c[j] - mid[i]) * (c[j] - mid[i]);
        var sd = Math.sqrt(s / n);
        up.push(mid[i] + m * sd); lo.push(mid[i] - m * sd);
      }
      return {mid:mid, up:up, lo:lo};
    },
    rsi: function(c, n){
      var out = [null], g = 0, l = 0;
      for(var i = 1; i < c.length; i++){
        var d = c[i] - c[i - 1], up = d > 0 ? d : 0, dn = d < 0 ? -d : 0;
        if(i <= n){
          g += up; l += dn;
          if(i === n){ g /= n; l /= n; out.push(l === 0 ? 100 : 100 - 100 / (1 + g / l)); } else out.push(null);
        }else{
          g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n;
          out.push(l === 0 ? 100 : 100 - 100 / (1 + g / l));
        }
      }
      return out;
    },
    macd: function(c, f, s, sig){
      var a = TA.ema(c, f), b = TA.ema(c, s);
      var m = a.map(function(v, i){ return v === null || b[i] === null ? null : v - b[i]; });
      var sg = TA.ema(m, sig);
      return {macd:m, signal:sg, hist:m.map(function(v, i){ return v === null || sg[i] === null ? null : v - sg[i]; })};
    },
    stoch: function(h, l, c, n, sk, sd){
      var raw = [];
      for(var i = 0; i < c.length; i++){
        if(i < n - 1){ raw.push(null); continue; }
        var hh = -Infinity, ll = Infinity;
        for(var j = i - n + 1; j <= i; j++){ if(h[j] > hh) hh = h[j]; if(l[j] < ll) ll = l[j]; }
        raw.push(hh === ll ? 50 : (c[i] - ll) / (hh - ll) * 100);
      }
      function smaN(a, k){
        var out = [], buf = [];
        a.forEach(function(v){
          if(v === null){ out.push(null); return; }
          buf.push(v); if(buf.length > k) buf.shift();
          out.push(buf.length === k ? buf.reduce(function(x, y){ return x + y; }, 0) / k : null);
        });
        return out;
      }
      var k = smaN(raw, sk);
      return {k:k, d:smaN(k, sd)};
    },
    sar: function(h, l, step, max){
      var n = h.length, out = new Array(n).fill(null);
      if(n < 2) return out;
      var up = h[1] >= h[0], af = step, ep = up ? Math.max(h[0], h[1]) : Math.min(l[0], l[1]);
      var sar = up ? Math.min(l[0], l[1]) : Math.max(h[0], h[1]);
      out[1] = sar;
      for(var i = 2; i < n; i++){
        sar = sar + af * (ep - sar);
        if(up){
          sar = Math.min(sar, l[i - 1], l[i - 2]);
          if(l[i] < sar){ up = false; sar = ep; ep = l[i]; af = step; }
          else if(h[i] > ep){ ep = h[i]; af = Math.min(af + step, max); }
        }else{
          sar = Math.max(sar, h[i - 1], h[i - 2]);
          if(h[i] > sar){ up = true; sar = ep; ep = h[i]; af = step; }
          else if(l[i] < ep){ ep = l[i]; af = Math.min(af + step, max); }
        }
        out[i] = sar;
      }
      return out;
    }
  };

  // danh sách chỉ báo cho người dùng chọn
  var CHI_BAO = [
    {id:'vol', ten:'Khối lượng', nhom:'gia'},
    {id:'ma20', ten:'MA 20', nhom:'gia', mau:'#F0B429'},
    {id:'ma50', ten:'MA 50', nhom:'gia', mau:'#8DA6EC'},
    {id:'ma200', ten:'MA 200', nhom:'gia', mau:'#E879F9'},
    {id:'ema20', ten:'EMA 20', nhom:'gia', mau:'#2DD4BF'},
    {id:'bb', ten:'Bollinger Bands (20, 2)', nhom:'gia', mau:'#60A5FA'},
    {id:'sar', ten:'Parabolic SAR (0,02; 0,2)', nhom:'gia', mau:'#FDE047'},
    {id:'rsi', ten:'RSI (14)', nhom:'khung', mau:'#C084FC'},
    {id:'macd', ten:'MACD (12, 26, 9)', nhom:'khung', mau:'#60A5FA'},
    {id:'stoch', ten:'Stochastic (14, 3, 3)', nhom:'khung', mau:'#F0B429'}
  ];
  var CB = {};
  CHI_BAO.forEach(function(x){ CB[x.id] = x; });

  function StockModal(getList){
    var overlay = $('#smOverlay'), dialog = $('.sm', overlay);
    var chartBox = $('#smChart'), legend = $('#smLegend');
    var UP = '#3DD15C', DOWN = '#FF6B61';
    var L = null, chart = null, data = null, calc = null, current = null, months = 6, type = 'nen', lastFocus = null;
    var mainSeries = null;
    var active = (function(){
      try{
        var v = JSON.parse(localStorage.getItem('kcn-chi-bao'));
        if(Array.isArray(v)) return v.filter(function(id){ return CB[id]; });
      }catch(e){}
      return ['vol', 'ma20', 'ma50'];
    })();
    function saveActive(){ try{ localStorage.setItem('kcn-chi-bao', JSON.stringify(active)); }catch(e){} }
    function on(id){ return active.indexOf(id) > -1; }

    // ---------- menu chọn chỉ báo
    var menu = $('#smIndMenu'), menuBtn = $('#smIndBtn');
    function renderMenu(){
      var h = '';
      [['gia', 'Trên biểu đồ giá'], ['khung', 'Khung riêng bên dưới']].forEach(function(g){
        h += '<p class="sm-ind-group">' + g[1] + '</p>';
        CHI_BAO.filter(function(x){ return x.nhom === g[0]; }).forEach(function(x){
          h += '<label><input type="checkbox" value="' + x.id + '"' + (on(x.id) ? ' checked' : '') + '>' +
            '<i style="background:' + (x.mau || '#5B6B9C') + '"></i>' + x.ten + '</label>';
        });
      });
      menu.innerHTML = h;
      $('#smIndCount').textContent = active.length ? '(' + active.length + ')' : '';
      $('#smIndChips').innerHTML = active.map(function(id){
        return '<button type="button" class="sm-chip-ind" data-id="' + id + '" aria-label="Bỏ ' + CB[id].ten + '">' +
          '<i style="background:' + (CB[id].mau || '#5B6B9C') + '"></i>' + CB[id].ten.replace(/ \(.*\)/, '') + ' <span aria-hidden="true">×</span></button>';
      }).join('');
    }
    function toggle(id, val){
      active = active.filter(function(x){ return x !== id; });
      if(val) active.push(id);
      saveActive(); renderMenu();
      if(current){ try{ history.replaceState(null, '', '#ma=' + current + '&cb=' + active.join(',')); }catch(e){} }
      if(data && L) rebuild();
    }
    menuBtn.addEventListener('click', function(e){
      e.stopPropagation();
      var open = menu.hidden;
      menu.hidden = !open;
      menuBtn.setAttribute('aria-expanded', String(open));
    });
    menu.addEventListener('change', function(e){ if(e.target.value) toggle(e.target.value, e.target.checked); });
    menu.addEventListener('click', function(e){ e.stopPropagation(); });
    $('#smIndChips').addEventListener('click', function(e){
      var b = e.target.closest('.sm-chip-ind'); if(b) toggle(b.getAttribute('data-id'), false);
    });
    overlay.addEventListener('click', function(){ if(!menu.hidden){ menu.hidden = true; menuBtn.setAttribute('aria-expanded', 'false'); } });
    renderMenu();

    // ---------- tính toán
    function compute(){
      var d = data;
      calc = {
        ma20: TA.sma(d.c, 20), ma50: TA.sma(d.c, 50), ma200: TA.sma(d.c, 200), ema20: TA.ema(d.c, 20),
        bb: TA.bb(d.c, 20, 2), sar: TA.sar(d.h, d.l, 0.02, 0.2), rsi: TA.rsi(d.c, 14),
        macd: TA.macd(d.c, 12, 26, 9), stoch: TA.stoch(d.h, d.l, d.c, 14, 3, 3)
      };
    }
    function pts(arr, colorFn){
      var out = [];
      arr.forEach(function(v, i){
        if(v === null || v === undefined || isNaN(v)) return;
        var p = {time:data.d[i], value:v};
        if(colorFn) p.color = colorFn(v, i);
        out.push(p);
      });
      return out;
    }

    // ---------- dựng lại biểu đồ (mỗi khi đổi mã hoặc đổi chỉ báo)
    function rebuild(){
      var keep = chart ? chart.timeScale().getVisibleLogicalRange() : null;
      if(chart){ chart.remove(); chart = null; }
      var osc = active.filter(function(id){ return CB[id].nhom === 'khung'; });
      chartBox.style.height = (window.innerWidth < 900 ? 330 : 430) + osc.length * 130 + 'px';
      chart = L.createChart(chartBox, {
        autoSize: true,
        layout: {background: {type: 'solid', color: 'transparent'}, textColor: '#AEB9DB', fontFamily: '"JetBrains Mono", monospace', fontSize: 11,
          panes: {separatorColor: '#2B3F86', separatorHoverColor: 'rgba(198,224,16,.25)', enableResize: true}},
        grid: {vertLines: {color: 'rgba(43,63,134,.35)'}, horzLines: {color: 'rgba(43,63,134,.35)'}},
        rightPriceScale: {borderColor: '#2B3F86', minimumWidth: 72},
        timeScale: {borderColor: '#2B3F86', rightOffset: 4, minBarSpacing: 1},
        crosshair: {mode: 0},
        localization: {
          locale: 'vi-VN',
          priceFormatter: function(p){ return Math.abs(p) >= 1000 ? fmt(p) : fmt(p, 2); },
          timeFormatter: function(t){ return ngayVN(typeof t === 'string' ? t : t.year + '-' + ('0' + t.month).slice(-2) + '-' + ('0' + t.day).slice(-2)); }
        }
      });
      var d = data, lw = {priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false};
      function line(arr, color, pane, extra){
        var o = {color: color, lineWidth: 1}; for(var k in lw) o[k] = lw[k]; for(var e in extra || {}) o[e] = extra[e];
        var s = chart.addSeries(L.LineSeries, o, pane || 0); s.setData(pts(arr)); return s;
      }

      // giá
      if(type === 'nen'){
        mainSeries = chart.addSeries(L.CandlestickSeries, {upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
          priceFormat: {type: 'price', precision: 0, minMove: 10}});
        mainSeries.setData(d.d.map(function(t, i){ return {time: t, open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i]}; }));
      }else{
        mainSeries = chart.addSeries(L.AreaSeries, {lineColor: '#8DA6EC', topColor: 'rgba(141,166,236,.28)', bottomColor: 'rgba(141,166,236,0)', lineWidth: 2,
          priceFormat: {type: 'price', precision: 0, minMove: 10}});
        mainSeries.setData(pts(d.c));
      }
      mainSeries.priceScale().applyOptions({scaleMargins: {top: 0.08, bottom: on('vol') ? 0.24 : 0.06}});

      if(on('vol')){
        var vol = chart.addSeries(L.HistogramSeries, {priceFormat: {type: 'volume'}, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false});
        vol.priceScale().applyOptions({scaleMargins: {top: 0.82, bottom: 0}});
        vol.setData(d.d.map(function(t, i){ return {time: t, value: d.v[i], color: d.c[i] >= d.o[i] ? 'rgba(61,209,92,.4)' : 'rgba(255,107,97,.4)'}; }));
      }
      ['ma20', 'ma50', 'ma200', 'ema20'].forEach(function(id){ if(on(id)) line(calc[id], CB[id].mau); });
      if(on('bb')){
        line(calc.bb.up, 'rgba(96,165,250,.85)');
        line(calc.bb.mid, 'rgba(96,165,250,.55)', 0, {lineStyle: 2});
        line(calc.bb.lo, 'rgba(96,165,250,.85)');
      }
      if(on('sar')){
        line(calc.sar, CB.sar.mau, 0, {lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 1.6});
      }

      // khung riêng
      var pane = 0;
      osc.forEach(function(id){
        pane++;
        if(id === 'rsi'){
          var r = line(calc.rsi, CB.rsi.mau, pane, {lineWidth: 1.5, lastValueVisible: true, priceFormat: {type: 'price', precision: 1, minMove: 0.1}});
          r.createPriceLine({price: 70, color: 'rgba(255,107,97,.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false});
          r.createPriceLine({price: 30, color: 'rgba(61,209,92,.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false});
        }else if(id === 'macd'){
          var hs = chart.addSeries(L.HistogramSeries, {priceLineVisible: false, lastValueVisible: false, priceFormat: {type: 'price', precision: 0, minMove: 1}}, pane);
          hs.setData(pts(calc.macd.hist, function(v){ return v >= 0 ? 'rgba(61,209,92,.55)' : 'rgba(255,107,97,.55)'; }));
          line(calc.macd.macd, '#60A5FA', pane, {lineWidth: 1.5, lastValueVisible: true, priceFormat: {type: 'price', precision: 0, minMove: 1}});
          line(calc.macd.signal, '#F0B429', pane, {lineWidth: 1.2, priceFormat: {type: 'price', precision: 0, minMove: 1}});
        }else if(id === 'stoch'){
          var k = line(calc.stoch.k, '#60A5FA', pane, {lineWidth: 1.5, lastValueVisible: true, priceFormat: {type: 'price', precision: 1, minMove: 0.1}});
          line(calc.stoch.d, '#F0B429', pane, {lineWidth: 1.2, priceFormat: {type: 'price', precision: 1, minMove: 0.1}});
          k.createPriceLine({price: 80, color: 'rgba(255,107,97,.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false});
          k.createPriceLine({price: 20, color: 'rgba(61,209,92,.6)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false});
        }
      });
      var panes = chart.panes();
      // chia chiều cao: khung giá chiếm phần lớn, mỗi khung chỉ báo một phần bằng nhau
      panes.forEach(function(p, i){ p.setStretchFactor(i === 0 ? 3.3 : 1); });

      chart.subscribeCrosshairMove(function(p){
        var i = d.d.length - 1;
        if(p && p.time){
          var t = typeof p.time === 'string' ? p.time : (p.time.year ? p.time.year + '-' + ('0' + p.time.month).slice(-2) + '-' + ('0' + p.time.day).slice(-2) : null);
          if(t){ var k2 = d.d.lastIndexOf(t); if(k2 > -1) i = k2; }
        }
        showLegend(i);
      });
      if(keep) chart.timeScale().setVisibleLogicalRange(keep); else setRange();
      showLegend(d.d.length - 1);
    }

    function v(x, dg){ return x === null || x === undefined || isNaN(x) ? '–' : fmt(x, dg); }
    function showLegend(i){
      var d = data, prev = i > 0 ? d.c[i - 1] : d.c[i], ch = (d.c[i] / prev - 1) * 100;
      var c = d.c[i] >= d.o[i] ? 'up' : 'down';
      var h = '<div><span>' + ngayVN(d.d[i]) + '</span>' +
        '<span>Mở <b class="' + c + '">' + fmt(d.o[i]) + '</b></span>' +
        '<span>Cao <b class="' + c + '">' + fmt(d.h[i]) + '</b></span>' +
        '<span>Thấp <b class="' + c + '">' + fmt(d.l[i]) + '</b></span>' +
        '<span>Đóng <b class="' + c + '">' + fmt(d.c[i]) + '</b></span>' +
        '<span><b class="' + cls(ch) + '">' + pct(ch) + '</b></span>' +
        (on('vol') ? '<span>KL <b>' + fmt(d.v[i]) + '</b></span>' : '') + '</div>';
      var ind = [];
      ['ma20', 'ma50', 'ma200', 'ema20'].forEach(function(id){
        if(on(id)) ind.push('<span style="color:' + CB[id].mau + '">' + CB[id].ten.replace(' ', '') + ' <b>' + v(calc[id][i]) + '</b></span>');
      });
      if(on('bb')) ind.push('<span style="color:' + CB.bb.mau + '">BB <b>' + v(calc.bb.lo[i]) + ' – ' + v(calc.bb.up[i]) + '</b></span>');
      if(on('sar')) ind.push('<span style="color:' + CB.sar.mau + '">SAR <b>' + v(calc.sar[i]) + '</b></span>');
      if(on('rsi')) ind.push('<span style="color:' + CB.rsi.mau + '">RSI <b>' + v(calc.rsi[i], 1) + '</b></span>');
      if(on('macd')) ind.push('<span style="color:#60A5FA">MACD <b>' + v(calc.macd.macd[i]) + '</b> / <b style="color:#F0B429">' + v(calc.macd.signal[i]) + '</b></span>');
      if(on('stoch')) ind.push('<span style="color:#60A5FA">%K <b>' + v(calc.stoch.k[i], 1) + '</b> <b style="color:#F0B429">%D ' + v(calc.stoch.d[i], 1) + '</b></span>');
      legend.innerHTML = h + (ind.length ? '<div>' + ind.join('') + '</div>' : '');
    }

    function setRange(){
      if(!chart || !data) return;
      if(!months){ chart.timeScale().fitContent(); return; }
      var end = new Date(data.d[data.d.length - 1]);
      var start = new Date(end); start.setMonth(start.getMonth() - months);
      chart.timeScale().setVisibleRange({from: start.toISOString().slice(0, 10), to: data.d[data.d.length - 1]});
    }

    function side(){
      var d = data, n = d.c.length, c = d.c[n - 1];
      var ref = d.tham_chieu || (n > 1 ? d.c[n - 2] : c);
      var ch = c - ref, p = ch / ref * 100;
      $('#smPrice').textContent = fmt(c);
      var chg = $('#smChg'); chg.className = 'sm-chg ' + cls(ch);
      chg.textContent = (ch >= 0 ? '+' : '−') + fmt(Math.abs(ch)) + ' (' + pct(p) + ')';
      $('#smTime').textContent = 'Cập nhật ' + moc(d.d[n - 1], d.cap_nhat_luc);

      var kl20 = 0, k = Math.min(20, n);
      for(var i = n - k; i < n; i++) kl20 += d.v[i];
      kl20 /= k;
      $('#smSession').innerHTML = [
        ['Tham chiếu', fmt(d.tham_chieu), 'ref'], ['Trần', fmt(d.tran), 'ceil'], ['Sàn', fmt(d.san_gia), 'floor'],
        ['Mở cửa', fmt(d.o[n - 1])], ['Cao nhất', fmt(d.h[n - 1])], ['Thấp nhất', fmt(d.l[n - 1])],
        ['Khối lượng', fmt(d.v[n - 1])], ['KL TB 20 phiên', fmt(kl20)],
        ['Giá trị (ước tính)', tien(c * d.v[n - 1])]
      ].map(function(x){ return '<div><dt>' + x[0] + '</dt><dd class="' + (x[2] || '') + '">' + x[1] + '</dd></div>'; }).join('');

      var from = Math.max(0, n - 252), lo = Infinity, hi = -Infinity;
      for(var j = from; j < n; j++){ if(d.l[j] < lo) lo = d.l[j]; if(d.h[j] > hi) hi = d.h[j]; }
      var pos = hi > lo ? (c - lo) / (hi - lo) * 100 : 50;
      $('#smWeek52').innerHTML = '<div class="w52"><div class="w52-bar"><i style="left:' + pos.toFixed(1) + '%"></i></div>' +
        '<div class="w52-lbl"><span>' + fmt(lo) + '</span><span>' + fmt(hi) + '</span></div>' +
        '<p>Giá hiện tại cách đỉnh ' + pct((c / hi - 1) * 100, 1) + ', cách đáy ' + pct((c / lo - 1) * 100, 1) + '</p></div>';

      var r = returns(d.d, d.c);
      $('#smPerf').innerHTML = [['1T', r['1m']], ['3T', r['3m']], ['6T', r['6m']], ['YTD', r.ytd], ['1N', r['1y']], ['3N', r['3y']]].map(function(x){
        return '<div><span>' + x[0] + '</span><b class="' + cls(x[1]) + '">' + pct(x[1], 1) + '</b></div>';
      }).join('');

      var cb = d.co_ban || {};
      $('#smKy').textContent = cb.ky ? '(quý ' + cb.ky.replace(' Q', '/Q').split('/').reverse().join('/') + ')' : '';
      var von = d.co_phieu_niem_yet ? c * d.co_phieu_niem_yet : null;
      function num(x, dg, suf){ return x === null || x === undefined ? '–' : fmt(x, dg) + (suf || ''); }
      $('#smFund').innerHTML = [
        ['Vốn hoá', von ? fmt(von / 1e9, 0) + ' tỷ' : '–'],
        ['EPS 4 quý', num(cb.eps, 0, ' đ')],
        ['P/E', cb.eps > 0 ? fmt(c / cb.eps, 1) : '–'],
        ['BVPS', num(cb.bvps, 0, ' đ')],
        ['P/B', cb.bvps > 0 ? fmt(c / cb.bvps, 2) : '–'],
        ['ROE 4 quý', num(cb.roe, 1, '%')],
        ['ROA 4 quý', num(cb.roa, 1, '%')],
        ['Biên LN ròng', num(cb.bien_ln_rong, 1, '%')],
        ['Nợ vay / VCSH', num(cb.no_vay_vcsh, 1, '%')],
        ['Beta', num(cb.beta, 2)]
      ].map(function(x){ return '<div><dt>' + x[0] + '</dt><dd>' + x[1] + '</dd></div>'; }).join('');
    }

    function open(maCk, row){
      current = maCk;
      if(overlay.hidden){
        lastFocus = document.activeElement;
        overlay.hidden = false;
        document.body.classList.add('modal-open');
      }
      $('#smCode').textContent = maCk;
      $('#smName').textContent = row ? row.ten : '';
      $('#smSector').textContent = row ? row.nganh : '';
      legend.textContent = 'Đang tải dữ liệu…';
      try{ history.replaceState(null, '', '#ma=' + maCk + '&cb=' + active.join(',')); }catch(e){}
      dialog.focus();
      Promise.all([loadLwc(), load('cp/' + maCk + '.json')]).then(function(res){
        if(current !== maCk) return;
        L = res[0]; data = res[1];
        $('#smName').textContent = data.ten;
        $('#smSector').textContent = data.nganh;
        compute();
        side();
        if(chart){ chart.remove(); chart = null; }
        rebuild();
      }).catch(function(){
        legend.textContent = 'Chưa tải được dữ liệu của mã này. Vui lòng thử lại sau.';
      });
    }

    function close(){
      overlay.hidden = true;
      menu.hidden = true;
      document.body.classList.remove('modal-open');
      current = null;
      try{ history.replaceState(null, '', location.pathname + location.search); }catch(e){}
      if(lastFocus) lastFocus.focus();
    }

    function step(k){
      var list = getList(), i = -1;
      list.forEach(function(x, j){ if(x.ma === current) i = j; });
      if(i < 0 || !list.length) return;
      var nx = list[(i + k + list.length) % list.length];
      open(nx.ma, nx);
    }

    $('#smClose').addEventListener('click', close);
    $('#smPrev').addEventListener('click', function(){ step(-1); });
    $('#smNext').addEventListener('click', function(){ step(1); });
    overlay.addEventListener('click', function(e){ if(e.target === overlay) close(); });
    document.addEventListener('keydown', function(e){
      if(overlay.hidden) return;
      if(e.key === 'Escape'){ if(!menu.hidden){ menu.hidden = true; menuBtn.focus(); } else close(); }
      else if(e.key === 'ArrowLeft' && e.target.tagName !== 'INPUT') step(-1);
      else if(e.key === 'ArrowRight' && e.target.tagName !== 'INPUT') step(1);
      else if(e.key === 'Tab'){
        var f = $$('button, input, [tabindex="0"]', dialog).filter(function(x){ return x.offsetParent !== null; });
        if(!f.length) return;
        if(e.shiftKey && document.activeElement === f[0]){ e.preventDefault(); f[f.length - 1].focus(); }
        else if(!e.shiftKey && document.activeElement === f[f.length - 1]){ e.preventDefault(); f[0].focus(); }
      }
    });
    bindRange($('#smRange'), months, function(m){ months = m; setRange(); });
    $$('#smType button').forEach(function(b){
      b.addEventListener('click', function(){
        type = b.getAttribute('data-t');
        $$('#smType button').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
        if(data && L) rebuild();
      });
    });

    function setActive(list){
      active = list.filter(function(id){ return CB[id]; });
      saveActive(); renderMenu();
      if(data && L) rebuild();
    }

    return {open: open, setActive: setActive};
  }

  // =====================================================================
  // TRANG THỊ TRƯỜNG
  // =====================================================================
  var mkt = $('#mktChart');
  if(mkt){
    Promise.all([load('chi_so.json'), load('co_phieu.json')]).then(function(res){
      var cs = res[0], cp = res[1];
      var keys = ['VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX'].filter(function(k){ return cs[k]; });
      var current = keys[0], months = 3;
      $('#mktDate').textContent = moc(cp.cap_nhat, cp.cap_nhat_luc);

      $('#mktCards').innerHTML = keys.map(function(k, i){
        var s = cs[k], n = s.c.length, ch = s.c[n - 1] - s.c[n - 2], p = (s.c[n - 1] / s.c[n - 2] - 1) * 100;
        return '<button class="index-card" type="button" data-k="' + k + '" aria-pressed="' + (i === 0) + '">' +
          '<p class="name">' + esc(s.ten) + '</p><p class="val tabular">' + fmt(s.c[n - 1], 2) + '</p>' +
          '<span class="chg ' + cls(ch) + '">' + (ch >= 0 ? '▲ +' : '▼ −') + fmt(Math.abs(ch), 2) + ' (' + pct(p).replace(/^[+−]/, '') + ')</span></button>';
      }).join('');

      var chart = LineChart(mkt, {label:'Diễn biến chỉ số', area:true, yDigits:0});
      function draw(){
        var s = cs[current];
        chart.render([{name:s.ten, color:'#3DD15C', d:s.d, c:s.c}], months, false);
        // đổi màu đường theo kết quả trong kỳ đang xem
        var path = mkt.querySelectorAll('svg path');
        var ret = null;
        if(path.length){
          var leg = mkt.querySelector('.lc-legend b');
          var down = leg && leg.classList.contains('down');
          path.forEach(function(p){
            if(p.getAttribute('stroke')) p.setAttribute('stroke', down ? '#FF6B61' : '#3DD15C');
            else p.setAttribute('fill', down ? '#FF6B61' : '#3DD15C');
          });
        }
        ret = returns(s.d, s.c);
        $('#mktRet').innerHTML = KY.map(function(k){
          return '<span>' + k[1] + ' <b class="' + cls(ret[k[0]]) + '">' + pct(ret[k[0]]) + '</b></span>';
        }).join('');
      }
      $$('#mktCards .index-card').forEach(function(b){
        b.addEventListener('click', function(){
          current = b.getAttribute('data-k');
          $$('#mktCards .index-card').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
          draw();
        });
      });
      bindRange($('#mktRange'), months, function(m){ months = m; draw(); });
      draw();

      // bảng cổ phiếu VN30
      var rows = cp.co_phieu, sortKey = 'ma', dir = 1, filter = '', shown = rows;
      var modal = StockModal(function(){ return shown.length ? shown : rows; });
      var q = new URLSearchParams(location.search).get('q');
      var search = $('#siteSearch');
      if(q){ filter = q.trim().toUpperCase(); if(search) search.value = q; }
      var body = $('#wlBody');
      function table(){
        var list = rows.filter(function(s){
          return !filter || s.ma.indexOf(filter) > -1 || s.ten.toUpperCase().indexOf(filter) > -1 || s.nganh.toUpperCase().indexOf(filter) > -1;
        }).sort(function(a, b){
          var x = a[sortKey], y = b[sortKey];
          return (typeof x === 'string' ? x.localeCompare(y, 'vi') : x - y) * dir;
        });
        shown = list;
        if(!list.length){ body.innerHTML = '<div class="wl-empty">Không tìm thấy "' + esc(filter) + '" trong rổ VN30.</div>'; return; }
        body.innerHTML = list.map(function(s){
          return '<div class="wl-row wl-click" role="row" tabindex="0" data-ma="' + esc(s.ma) + '" aria-label="Xem chi tiết ' + esc(s.ma) + '">' +
            '<span class="wl-ticker" role="cell">' + esc(s.ma) + '</span>' +
            '<span class="wl-name" role="cell">' + esc(s.ten) + '<small>' + esc(s.nganh) + '</small></span>' +
            '<span class="wl-num tabular" role="cell">' + fmt(s.gia) + '</span>' +
            '<span class="wl-num tabular ' + cls(s.thay_doi) + '" role="cell">' + pct(s.thay_doi) + '</span>' +
            '<span class="wl-num tabular wl-vol" role="cell">' + fmt(s.khoi_luong / 1e6, 2) + ' tr</span>' +
            '<span class="wl-spark" role="cell">' + sparkSvg(s.spark, 64, 24, s.spark[s.spark.length - 1] >= s.spark[0] ? '#3DD15C' : '#FF6B61') + '</span></div>';
        }).join('');
      }
      $$('.wl-head button').forEach(function(btn){
        btn.addEventListener('click', function(){
          var k = btn.getAttribute('data-sort');
          if(k === sortKey) dir = -dir; else { sortKey = k; dir = (k === 'ma' || k === 'ten') ? 1 : -1; }
          $$('.wl-head button').forEach(function(b){
            $('.arrow', b).textContent = b === btn ? (dir > 0 ? '↑' : '↓') : '';
            b.parentNode.setAttribute('aria-sort', b === btn ? (dir > 0 ? 'ascending' : 'descending') : 'none');
          });
          table();
        });
      });
      if(search) search.addEventListener('input', function(){ filter = search.value.trim().toUpperCase(); table(); });
      function openRow(el){
        var m = el.getAttribute('data-ma');
        modal.open(m, rows.filter(function(x){ return x.ma === m; })[0]);
      }
      body.addEventListener('click', function(e){ var r = e.target.closest('.wl-click'); if(r) openRow(r); });
      body.addEventListener('keydown', function(e){
        var r = e.target.closest('.wl-click');
        if(r && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); openRow(r); }
      });
      table();
      // mở thẳng popup khi link có dạng /thi-truong/#ma=FPT
      var h = location.hash.match(/ma=([A-Z0-9]+)/i);
      if(h){
        var m0 = h[1].toUpperCase(), r0 = rows.filter(function(x){ return x.ma === m0; })[0];
        var cbm = location.hash.match(/cb=([a-z0-9,]*)/i);
        if(cbm) modal.setActive(cbm[1] ? cbm[1].toLowerCase().split(',') : []);
        if(r0) modal.open(m0, r0);
      }
    }).catch(function(){ fail(mkt); });
  }

  // =====================================================================
  // TRANG DANH SÁCH ETF
  // =====================================================================
  var etfTable = $('#etfTable');
  if(etfTable){
    Promise.all([load('etf.json'), load('chi_so.json')]).then(function(res){
      var data = res[0], cs = res[1], quy = data.quy;
      $('#etfDate').textContent = moc(data.cap_nhat, data.cap_nhat_luc);

      // thẻ tổng quan
      var tongGt = quy.reduce(function(s, q){ return s + (q.gtgd_20 || 0); }, 0);
      var top = quy.filter(function(q){ return q.loi_nhuan['1y'] !== null; }).sort(function(a, b){ return b.loi_nhuan['1y'] - a.loi_nhuan['1y']; })[0];
      var vn30 = cs.VN30 ? returns(cs.VN30.d, cs.VN30.c)['1y'] : null;
      $('#etfKpis').innerHTML =
        '<div class="kpi"><span>Số quỹ ETF trên HOSE</span><b>' + quy.length + '</b></div>' +
        '<div class="kpi"><span>Giá trị giao dịch / phiên (TB 20 phiên)</span><b>' + tien(tongGt) + '</b></div>' +
        (top ? '<div class="kpi"><span>Tăng mạnh nhất 1 năm</span><b>' + esc(top.ma) + ' <small class="up">' + pct(top.loi_nhuan['1y']) + '</small></b></div>' : '') +
        '<div class="kpi"><span>Chỉ số VN30, 1 năm</span><b class="' + cls(vn30) + '">' + pct(vn30) + '</b></div>';

      // bộ lọc
      var nhom = ['Tất cả'].concat(['VN30', 'Diamond', 'Tài chính', 'VN100', 'VNX50', 'Khác'].filter(function(n){
        return quy.some(function(q){ return q.nhom === n; });
      }));
      var group = 'Tất cả', text = '', sortKey = 'gtgd_20', dir = -1;
      var params = new URLSearchParams(location.search);
      var chon = (params.get('ss') || 'E1VFVN30,FUEVFVND,FUESSVFL').split(',').filter(function(m){
        return quy.some(function(q){ return q.ma === m; });
      }).slice(0, 4);

      $('#etfChips').innerHTML = nhom.map(function(n){
        return '<button type="button" class="chip" aria-pressed="' + (n === group) + '">' + n + '</button>';
      }).join('');
      $$('#etfChips .chip').forEach(function(b){
        b.addEventListener('click', function(){
          group = b.textContent;
          $$('#etfChips .chip').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
          render();
        });
      });
      $('#etfFilter').addEventListener('input', function(e){ text = e.target.value.trim().toUpperCase(); render(); });

      function val(q, k){ return k.indexOf('r_') === 0 ? q.loi_nhuan[k.slice(2)] : q[k]; }
      function render(){
        var list = quy.filter(function(q){
          return (group === 'Tất cả' || q.nhom === group) &&
            (!text || q.ma.indexOf(text) > -1 || q.ten.toUpperCase().indexOf(text) > -1);
        }).sort(function(a, b){
          var x = val(a, sortKey), y = val(b, sortKey);
          if(x === null || x === undefined) return 1;
          if(y === null || y === undefined) return -1;
          return (typeof x === 'string' ? x.localeCompare(y) : x - y) * dir;
        });
        var link = BASE + '/etf/chi-tiet/?ma=';
        $('#etfBody').innerHTML = list.length ? list.map(function(q){
          var L = q.loi_nhuan, on = chon.indexOf(q.ma) > -1;
          var up = q.spark[q.spark.length - 1] >= q.spark[0];
          return '<tr>' +
            '<td class="cmp"><input type="checkbox" aria-label="So sánh ' + q.ma + '" data-ma="' + q.ma + '"' + (on ? ' checked' : '') + '></td>' +
            '<td class="fund"><a href="' + link + q.ma + '"><b>' + q.ma + '</b><span>' + esc(q.ten) + '</span></a></td>' +
            '<td class="hide-md">' + (q.tham_chieu ? esc(cs[q.tham_chieu] ? cs[q.tham_chieu].ten : q.tham_chieu) : '–') + '</td>' +
            '<td class="num">' + fmt(q.gia) + '</td>' +
            '<td class="num ' + cls(L['1d']) + '">' + pct(L['1d']) + '</td>' +
            '<td class="num hide-sm ' + cls(L['1m']) + '">' + pct(L['1m']) + '</td>' +
            '<td class="num hide-sm ' + cls(L.ytd) + '">' + pct(L.ytd) + '</td>' +
            '<td class="num ' + cls(L['1y']) + '">' + pct(L['1y']) + '</td>' +
            '<td class="num hide-md ' + cls(L['3y']) + '">' + pct(L['3y']) + '</td>' +
            '<td class="num hide-md">' + tien(q.gtgd_20) + '</td>' +
            '<td class="spark hide-sm">' + sparkSvg(q.spark, 72, 26, up ? css('--good') : css('--critical')) + '</td>' +
          '</tr>';
        }).join('') : '<tr><td colspan="11" class="empty-row">Không có quỹ phù hợp.</td></tr>';
        $$('#etfBody input[type=checkbox]').forEach(function(cb){
          cb.addEventListener('change', function(){
            var m = cb.getAttribute('data-ma');
            if(cb.checked){
              if(chon.length >= 4){ cb.checked = false; alert('So sánh tối đa 4 quỹ cùng lúc.'); return; }
              chon.push(m);
            }else chon = chon.filter(function(x){ return x !== m; });
            drawCompare();
          });
        });
      }
      $$('#etfHead button').forEach(function(btn){
        btn.addEventListener('click', function(){
          var k = btn.getAttribute('data-sort');
          if(k === sortKey) dir = -dir; else { sortKey = k; dir = (k === 'ma') ? 1 : -1; }
          $$('#etfHead button').forEach(function(b){
            $('.arrow', b).textContent = b === btn ? (dir > 0 ? '↑' : '↓') : '';
            b.closest('th').setAttribute('aria-sort', b === btn ? (dir > 0 ? 'ascending' : 'descending') : 'none');
          });
          render();
        });
      });
      render();

      // so sánh hiệu suất
      var cmpChart = LineChart($('#etfCompare'), {label:'So sánh hiệu suất các quỹ ETF'});
      var months = 12, withIndex = true;
      function drawCompare(){
        var cols = palette();
        Promise.all(chon.map(function(m){ return load('etf/' + m + '.json'); })).then(function(hs){
          var series = hs.map(function(h, i){ return {name:h.ma, color:cols[i % cols.length], d:h.d, c:h.c}; });
          if(withIndex && cs.VN30) series.push({name:'Chỉ số VN30', color:css('--muted'), d:cs.VN30.d, c:cs.VN30.c});
          if(!series.length){ $('#etfCompareHint').hidden = false; }
          else { $('#etfCompareHint').hidden = true; }
          cmpChart.render(series, months, true);
          var u = new URL(location.href); u.searchParams.set('ss', chon.join(','));
          history.replaceState(null, '', u);
        });
      }
      bindRange($('#etfRange'), months, function(m){ months = m; drawCompare(); });
      $('#etfWithIndex').addEventListener('change', function(e){ withIndex = e.target.checked; drawCompare(); });
      drawCompare();
    }).catch(function(){ fail($('#etfBody').parentNode.parentNode); });
  }

  // =====================================================================
  // TRANG CHI TIẾT ETF
  // =====================================================================
  var etfDetail = $('#etfDetail');
  if(etfDetail){
    var ma = (new URLSearchParams(location.search).get('ma') || '').toUpperCase();
    Promise.all([load('etf.json'), load('chi_so.json')]).then(function(res){
      var q = res[0].quy.filter(function(x){ return x.ma === ma; })[0];
      var cs = res[1];
      if(!q){
        etfDetail.innerHTML = '<div class="empty-state"><p>Không tìm thấy quỹ ETF có mã <b>' + esc(ma || '(trống)') + '</b>.</p>' +
          '<a class="btn btn-accent" href="' + BASE + '/etf/">Xem danh sách ETF</a></div>';
        return;
      }
      document.title = q.ma + ' — ' + q.ten + ' | Kim Chỉ Nam';
      var lucCapNhat = res[0].cap_nhat_luc;
      return load('etf/' + ma + '.json').then(function(h){
        var tc = q.tham_chieu && cs[q.tham_chieu] ? cs[q.tham_chieu] : null;
        var L = q.loi_nhuan;
        $('#dCode').textContent = q.ma;
        $('#dName').textContent = q.ten_day_du;
        $('#dCrumb').textContent = q.ma;
        $('#dPrice').textContent = fmt(q.gia) + ' đ';
        var ch = $('#dChg'); ch.className = 'fund-chg ' + cls(L['1d']); ch.textContent = pct(L['1d']) + ' hôm nay';
        $('#dDate').textContent = 'Giá cập nhật ' + moc(q.ngay, lucCapNhat);
        $('#dCompare').href = BASE + '/etf/?ss=' + q.ma + (q.ma !== 'E1VFVN30' ? ',E1VFVN30' : ',FUEVFVND') + '#so-sanh';

        $('#dFacts').innerHTML = [
          ['Sàn niêm yết', 'HOSE'],
          ['Chỉ số tham chiếu', tc ? tc.ten : 'Chưa có dữ liệu chỉ số'],
          ['Dữ liệu giá từ', ngayVN(q.tu_ngay)],
          ['Giao dịch TB 20 phiên', tien(q.gtgd_20) + '/phiên'],
          ['Biến động 1 năm', q.bien_dong_1y === null ? '–' : fmt(q.bien_dong_1y, 1) + '%/năm'],
          ['Sụt giảm sâu nhất 1 năm', pct(q.sut_giam_1y, 1)]
        ].map(function(f){ return '<div><dt>' + f[0] + '</dt><dd>' + esc(f[1]) + '</dd></div>'; }).join('');

        var cols = palette(), months = 12;
        var chart = LineChart($('#dChart'), {label:'Hiệu suất ' + q.ma + ' so với chỉ số tham chiếu', area:true});
        function draw(){
          var s = [{name:q.ma, color:cols[0], d:h.d, c:h.c}];
          if(tc) s.push({name:tc.ten, color:css('--muted'), d:tc.d, c:tc.c});
          chart.render(s, months, true);
        }
        bindRange($('#dRange'), months, function(m){ months = m; draw(); });
        draw();

        var rows = [{name:q.ma + ' (giá thị trường)', color:cols[0], ret:L}];
        if(tc){
          var rt = returns(tc.d, tc.c), diff = {};
          KY.forEach(function(k){ diff[k[0]] = L[k[0]] === null || rt[k[0]] === null ? null : L[k[0]] - rt[k[0]]; });
          rows.push({name:tc.ten, color:css('--muted'), ret:rt});
          rows.push({name:'Chênh lệch', ret:diff, muted:true});
        }
        returnsTable($('#dReturns'), rows);
        dca(h);
      });
    }).catch(function(){ fail(etfDetail); });
  }

  // mô phỏng đầu tư định kỳ: mua vào phiên đầu tiên mỗi tháng theo giá đóng cửa
  function dca(h){
    var box = $('#dca');
    if(!box) return;
    var amount = $('#dcaAmount'), from = $('#dcaFrom');
    var years = {};
    h.d.forEach(function(d){ years[d.slice(0, 4)] = 1; });
    var ys = Object.keys(years).sort();
    var def = ys[Math.max(0, ys.length - 4)];
    from.innerHTML = ys.map(function(y){ return '<option' + (y === def ? ' selected' : '') + '>' + y + '</option>'; }).join('');
    var chart = LineChart($('#dcaChart'), {label:'Giá trị danh mục khi đầu tư định kỳ', yFmt:tien, minZero:true, noChange:true});
    function run(){
      var amt = Number(amount.value) * 1e6, y0 = from.value;
      $('#dcaAmountOut').textContent = fmt(Number(amount.value), 1) + ' triệu/tháng';
      var cc = 0, paid = 0, lastMonth = '', dates = [], value = [], invested = [];
      for(var i = 0; i < h.d.length; i++){
        if(h.d[i].slice(0, 4) < y0) continue;
        var m = h.d[i].slice(0, 7);
        if(m !== lastMonth){ cc += amt / h.c[i]; paid += amt; lastMonth = m; }
        dates.push(h.d[i]); value.push(cc * h.c[i]); invested.push(paid);
      }
      var cur = value[value.length - 1] || 0;
      $('#dcaPaid').textContent = tien(paid);
      $('#dcaValue').textContent = tien(cur);
      var g = $('#dcaGain'), gp = paid ? (cur / paid - 1) * 100 : 0;
      g.textContent = tien(cur - paid) + ' (' + pct(gp) + ')';
      g.className = 'tabular ' + cls(gp);
      chart.render([
        {name:'Giá trị danh mục', color:css('--s1'), d:dates, c:value},
        {name:'Tiền đã góp', color:css('--muted'), d:dates, c:invested}
      ], 0, false);
    }
    amount.addEventListener('input', run);
    from.addEventListener('change', run);
    run();
  }

  // =====================================================================
  // TRANG QUỸ MÔ PHỎNG
  // =====================================================================
  var fund = $('#fundPage');
  if(fund){
    Promise.all([load('quy_mo_phong.json'), load('chi_so.json'), load('etf/E1VFVN30.json').catch(function(){ return null; })]).then(function(res){
      var f = res[0], cs = res[1], e1 = res[2];
      var n = f.nav.length, L = f.loi_nhuan;
      $('#fNav').textContent = fmt(f.nav[n - 1], 2);
      var ch = $('#fChg'); ch.className = 'fund-chg ' + cls(L['1d']); ch.textContent = pct(L['1d']) + ' hôm nay';
      $('#fDate').textContent = 'NAV mô phỏng ' + moc(f.cap_nhat, f.cap_nhat_luc);
      $('#fSince').innerHTML = '<b class="' + cls(f.tu_dau) + '">' + pct(f.tu_dau) + '</b> từ ngày khởi đầu ' + ngayVN(f.ngay_khoi_dau) +
        ' · bình quân <b class="' + cls(f.tu_dau_nam) + '">' + pct(f.tu_dau_nam) + '</b>/năm';

      $('#fFacts').innerHTML = [
        ['Mã quỹ (mô phỏng)', f.ma],
        ['Ngày khởi đầu', ngayVN(f.ngay_khoi_dau)],
        ['NAV khởi đầu', fmt(f.nav_khoi_dau) + ' đ'],
        ['Chỉ số so sánh', 'VN30'],
        ['Phương pháp', 'Bình quyền ' + f.so_ma + ' mã'],
        ['Tái cân bằng', 'Đầu mỗi quý'],
        ['Lần gần nhất', ngayVN(f.tai_can_bang_gan_nhat)],
        ['Phí quản lý giả định', fmt(f.phi, 1) + '%/năm']
      ].map(function(x){ return '<div><dt>' + x[0] + '</dt><dd>' + esc(x[1]) + '</dd></div>'; }).join('');

      var cols = palette(), months = 12;
      var chart = LineChart($('#fChart'), {label:'Hiệu suất quỹ mô phỏng so với VN30', area:true});
      function draw(){
        var s = [{name:'KCN30 (mô phỏng)', color:cols[0], d:f.d, c:f.nav}];
        if(cs.VN30) s.push({name:'Chỉ số VN30', color:css('--muted'), d:cs.VN30.d, c:cs.VN30.c});
        if(e1) s.push({name:'E1VFVN30', color:cols[1], d:e1.d, c:e1.c});
        chart.render(s, months, true);
      }
      bindRange($('#fRange'), months, function(m){ months = m; draw(); });
      draw();

      var rows = [{name:'KCN30 (mô phỏng)', color:cols[0], ret:L}];
      if(cs.VN30) rows.push({name:'Chỉ số VN30', color:css('--muted'), ret:returns(cs.VN30.d, cs.VN30.c)});
      if(e1) rows.push({name:'E1VFVN30 (giá)', color:cols[1], ret:returns(e1.d, e1.c)});
      returnsTable($('#fReturns'), rows);

      $('#fRisk').innerHTML = [
        ['Biến động 1 năm', f.bien_dong_1y === null ? '–' : fmt(f.bien_dong_1y, 1) + '%', 'Độ lệch chuẩn lợi nhuận ngày, quy ra năm'],
        ['Sụt giảm sâu nhất 1 năm', pct(f.sut_giam_1y, 1), 'Mức giảm lớn nhất từ đỉnh xuống đáy'],
        ['Sụt giảm sâu nhất từ đầu', pct(f.sut_giam_tu_dau, 1), 'Tính từ ngày khởi đầu'],
        ['Beta so với VN30', f.beta_1y === null ? '–' : fmt(f.beta_1y, 2), 'Beta > 1: dao động mạnh hơn VN30'],
        ['Sai lệch so với VN30', f.sai_lech_1y === null ? '–' : fmt(f.sai_lech_1y, 1) + '%', 'Độ lệch lợi nhuận so với chỉ số, quy ra năm']
      ].map(function(x){ return '<div class="risk"><span>' + x[0] + '</span><b class="tabular">' + x[1] + '</b><small>' + x[2] + '</small></div>'; }).join('');

      // danh mục
      var full = false;
      function holdings(){
        var list = full ? f.danh_muc : f.danh_muc.slice(0, 10);
        $('#fHoldings').innerHTML = list.map(function(x, i){
          return '<tr><td class="num muted">' + (i + 1) + '</td><td><b>' + esc(x.ma) + '</b><span class="sub">' + esc(x.nganh) + ' · ' + esc(x.ten) + '</span></td>' +
            '<td class="num">' + fmt(x.gia) + '</td>' +
            '<td class="num ' + cls(x.thay_doi) + '">' + pct(x.thay_doi) + '</td>' +
            '<td class="num"><span class="wbar"><i style="width:' + Math.min(100, x.ty_trong / f.danh_muc[0].ty_trong * 100) + '%"></i></span>' + fmt(x.ty_trong, 2) + '%</td></tr>';
        }).join('');
        $('#fToggle').textContent = full ? 'Thu gọn, chỉ xem 10 mã lớn nhất' : 'Xem toàn bộ ' + f.danh_muc.length + ' mã';
      }
      $('#fToggle').addEventListener('click', function(){ full = !full; holdings(); });
      holdings();
      $('#fHoldDate').textContent = ngayVN(f.cap_nhat);

      $('#fCsv').addEventListener('click', function(){
        var lines = ['STT,Ma,Ten,Nganh,Gia (dong),Thay doi (%),Ty trong (%)'];
        f.danh_muc.forEach(function(x, i){
          lines.push([i + 1, x.ma, '"' + x.ten.replace(/"/g, '""') + '"', '"' + x.nganh + '"', x.gia, x.thay_doi, x.ty_trong].join(','));
        });
        var blob = new Blob(['﻿' + lines.join('\n')], {type:'text/csv;charset=utf-8'});
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'KCN30_danh_muc_' + f.cap_nhat + '.csv';
        document.body.appendChild(a); a.click(); a.remove();
      });

      donut($('#fDonut'), $('#fSectors'), f.nganh);
    }).catch(function(){ fail(fund); });
  }

  function donut(svgBox, legendBox, items){
    var colors = ['#264395', '#C6E010', '#4F86C6', '#E07B39', '#8AA2DA', '#2E9E8F', '#A3B800', '#7A5BA8', '#B9C3DC', '#5B6B8C', '#D9A441', '#9AA3B8'];
    var R = 60, C = 2 * Math.PI * R, off = 0, h = '';
    items.forEach(function(it, i){
      var len = it.ty_trong / 100 * C;
      h += '<circle cx="80" cy="80" r="' + R + '" fill="none" stroke="' + colors[i % colors.length] + '" stroke-width="26" ' +
        'stroke-dasharray="' + Math.max(0, len - 1.5).toFixed(2) + ' ' + (C - Math.max(0, len - 1.5)).toFixed(2) + '" stroke-dashoffset="' + (-off).toFixed(2) + '" transform="rotate(-90 80 80)">' +
        '<title>' + esc(it.nganh) + ': ' + fmt(it.ty_trong, 1) + '%</title></circle>';
      off += len;
    });
    svgBox.innerHTML = '<svg viewBox="0 0 160 160" role="img" aria-label="Phân bổ theo ngành">' + h +
      '<text x="80" y="76" text-anchor="middle" class="donut-num">' + items.length + '</text><text x="80" y="96" text-anchor="middle" class="donut-lbl">ngành</text></svg>';
    legendBox.innerHTML = items.map(function(it, i){
      return '<li><i style="background:' + colors[i % colors.length] + '"></i><span>' + esc(it.nganh) + '</span><b class="tabular">' + fmt(it.ty_trong, 1) + '%</b></li>';
    }).join('');
  }

  // =====================================================================
  // TRANG CHỦ
  // =====================================================================
  var homeFund = $('#homeFund');
  if(homeFund){
    load('quy_mo_phong.json').then(function(f){
      var n = f.nav.length;
      $('#hfNav').textContent = fmt(f.nav[n - 1], 2);
      var c = $('#hfChg'); c.className = 'fund-chg ' + cls(f.loi_nhuan['1d']); c.textContent = pct(f.loi_nhuan['1d']) + ' hôm nay';
      $('#hfStats').innerHTML = [['1 năm', f.loi_nhuan['1y']], ['3 năm', f.loi_nhuan['3y']], ['Từ đầu', f.tu_dau]].map(function(x){
        return '<div><span>' + x[0] + '</span><b class="' + cls(x[1]) + '">' + pct(x[1], 1) + '</b></div>';
      }).join('');
      $('#hfDate').textContent = 'NAV mô phỏng ' + moc(f.cap_nhat, f.cap_nhat_luc);
      $('#hfSpark').innerHTML = sparkSvg(f.nav.slice(-252), 300, 70, css('--s1'));
    }).catch(function(){});
  }
  var homeEtf = $('#homeEtf');
  if(homeEtf){
    load('etf.json').then(function(data){
      var top = data.quy.slice().sort(function(a, b){ return (b.gtgd_20 || 0) - (a.gtgd_20 || 0); }).slice(0, 4);
      homeEtf.innerHTML = top.map(function(q){
        var up = q.spark[q.spark.length - 1] >= q.spark[0];
        return '<a class="etf-mini" href="' + BASE + '/etf/chi-tiet/?ma=' + q.ma + '">' +
          '<div class="etf-mini-top"><b>' + q.ma + '</b><span class="' + cls(q.loi_nhuan['1d']) + '">' + pct(q.loi_nhuan['1d']) + '</span></div>' +
          '<p>' + esc(q.ten) + '</p>' +
          sparkSvg(q.spark, 220, 48, up ? css('--good') : css('--critical')) +
          '<div class="etf-mini-bot"><span>' + fmt(q.gia) + ' đ</span><span>1 năm <b class="' + cls(q.loi_nhuan['1y']) + '">' + pct(q.loi_nhuan['1y'], 1) + '</b></span></div></a>';
      }).join('');
      $('#homeEtfDate').textContent = moc(data.cap_nhat, data.cap_nhat_luc);
    }).catch(function(){ fail(homeEtf); });
  }
})();
