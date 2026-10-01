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
  // TRANG THỊ TRƯỜNG
  // =====================================================================
  var mkt = $('#mktChart');
  if(mkt){
    Promise.all([load('chi_so.json'), load('co_phieu.json')]).then(function(res){
      var cs = res[0], cp = res[1];
      var keys = ['VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX'].filter(function(k){ return cs[k]; });
      var current = keys[0], months = 3;
      $('#mktDate').textContent = ngayVN(cs[current].d[cs[current].d.length - 1]);

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
      var rows = cp.co_phieu, sortKey = 'ma', dir = 1, filter = '';
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
        if(!list.length){ body.innerHTML = '<div class="wl-empty">Không tìm thấy "' + esc(filter) + '" trong rổ VN30.</div>'; return; }
        body.innerHTML = list.map(function(s){
          return '<div class="wl-row" role="row">' +
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
      table();
    }).catch(function(){ fail(mkt); });
  }

  // =====================================================================
  // TRANG DANH SÁCH ETF
  // =====================================================================
  var etfTable = $('#etfTable');
  if(etfTable){
    Promise.all([load('etf.json'), load('chi_so.json')]).then(function(res){
      var data = res[0], cs = res[1], quy = data.quy;
      $('#etfDate').textContent = ngayVN(data.cap_nhat);

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
      return load('etf/' + ma + '.json').then(function(h){
        var tc = q.tham_chieu && cs[q.tham_chieu] ? cs[q.tham_chieu] : null;
        var L = q.loi_nhuan;
        $('#dCode').textContent = q.ma;
        $('#dName').textContent = q.ten_day_du;
        $('#dCrumb').textContent = q.ma;
        $('#dPrice').textContent = fmt(q.gia) + ' đ';
        var ch = $('#dChg'); ch.className = 'fund-chg ' + cls(L['1d']); ch.textContent = pct(L['1d']) + ' hôm nay';
        $('#dDate').textContent = 'Giá đóng cửa ngày ' + ngayVN(q.ngay);
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
      $('#fDate').textContent = 'NAV mô phỏng ngày ' + ngayVN(f.cap_nhat);
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
      $('#hfDate').textContent = 'NAV mô phỏng ngày ' + ngayVN(f.cap_nhat);
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
      $('#homeEtfDate').textContent = ngayVN(data.cap_nhat);
    }).catch(function(){ fail(homeEtf); });
  }
})();
