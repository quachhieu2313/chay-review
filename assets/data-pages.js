/* Kim Chỉ Nam — các trang dùng dữ liệu thật: Thị trường, ETF, quỹ nắm giữ và khuyến nghị */
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
  // giờ Việt Nam hiện tại (không phụ thuộc múi giờ máy người xem)
  function bayGioVN(){ return new Date(Date.now() + (new Date().getTimezoneOffset() + 420) * 60000); }
  // trong giờ giao dịch mà dữ liệu cũ hơn 25 phút thì coi là chậm
  function cham(ngay, luc){
    var n = bayGioVN(), thu = n.getDay(), phut = n.getHours() * 60 + n.getMinutes();
    if(thu === 0 || thu === 6) return false;
    // chỉ xét trong lúc sàn đang khớp lệnh: 9:25–11:35 và 13:25–14:50 (nghỉ trưa, sau ATC giá đứng yên là bình thường)
    var trongPhien = (phut >= 9 * 60 + 25 && phut <= 11 * 60 + 35) || (phut >= 13 * 60 + 25 && phut <= 14 * 60 + 50);
    if(!trongPhien) return false;
    var hom = n.getFullYear() + '-' + ('0' + (n.getMonth() + 1)).slice(-2) + '-' + ('0' + n.getDate()).slice(-2);
    if(ngay !== hom || !luc) return true;
    var p = luc.split(':');
    return phut - (Number(p[0]) * 60 + Number(p[1])) > 25;
  }
  function moc(ngay, luc){
    return ngayVN(ngay) + (luc ? ' lúc ' + luc : '') + (cham(ngay, luc) ? ' (dữ liệu đang chậm hơn dự kiến)' : '');
  }
  function cls(n){ return n > 0 ? 'up' : n < 0 ? 'down' : ''; }
  function ngayVN(s){ if(!s) return '–'; var p = s.split('-'); return p.length < 3 ? s : p[2] + '/' + p[1] + '/' + p[0]; }
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
  // ---------- phiên bản dữ liệu: phien.json ghi thời điểm cập nhật gần nhất.
  // Mọi file dữ liệu tải kèm ?v=<thời điểm> nên không bao giờ dính bản cũ trong bộ đệm.
  function docPhien(){
    return fetch(BASE + '/assets/data/phien.json?t=' + Date.now(), {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : {}; })
      .then(function(p){ return p && p.luc ? p.luc : ''; })
      .catch(function(){ return ''; });
  }
  var phienHienTai = docPhien();
  function load(path){
    if(!cache[path]){
      cache[path] = phienHienTai.then(function(v){
        return fetch(BASE + '/assets/data/' + path + '?v=' + encodeURIComponent(v || Date.now()), {cache:'no-cache'});
      }).then(function(r){
        if(!r.ok) throw new Error(path + ' ' + r.status);
        return r.json();
      }).catch(function(e){ delete cache[path]; throw e; });
    }
    return cache[path];
  }
  // chỉ số tách thành từng file nhỏ: chi_so/<MÃ>.json; trả về {mã: dữ liệu}
  function loadChiSo(keys){
    return Promise.all(keys.map(function(k){
      return load('chi_so/' + k + '.json').then(function(x){ return [k, x]; }).catch(function(){ return null; });
    })).then(function(ds){
      var out = {};
      ds.forEach(function(x){ if(x) out[x[0]] = x[1]; });
      return out;
    });
  }
  var CHI_SO_CHINH = ['VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX'];
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

  // ---- Cổ Phiếu Khuyến Nghị: xếp hạng thử nghiệm và backtest động lượng giá
  var recPage = $('#recPage');
  if(recPage){
    var recHorizon = '3m', recSide = 'mua';
    var recLabels = {
      dong_luong: 'Động lượng giá',
      chat_luong: 'Chất lượng tài chính',
      quy: 'Độ phủ danh mục quỹ',
      dinh_gia: 'Định giá',
      rui_ro: 'Rủi ro'
    };
    function veRecBang(data){
      var items = data.danh_sach[recHorizon] && data.danh_sach[recHorizon][recSide] || [];
      $('#recTitle').textContent = (recSide === 'mua' ? 'Top 10 mua theo bộ lọc' : 'Top 10 bán/giảm theo bộ lọc') + ' · ' + (recHorizon === '3m' ? '3 tháng' : '6 tháng');
      if(!items.length){
        $('#recTable').innerHTML = '<div class="empty-state">Chưa đủ dữ liệu để xếp hạng ở thời hạn này.</div>';
        return;
      }
      var table = '<table class="data-table rec-table"><thead><tr><th scope="col" class="num">#</th><th scope="col">Mã / doanh nghiệp</th><th scope="col" class="num">Điểm</th><th scope="col" class="num">3T</th><th scope="col" class="num">6T</th><th scope="col" class="num">ROE</th><th scope="col" class="num">P/E</th><th scope="col" class="num">Quỹ mở / ETF chỉ số*</th><th scope="col">Cảnh báo</th><th scope="col">Chi tiết</th></tr></thead><tbody>';
      table += items.map(function(x, i){
        var m = x.metrics || {}, warnings = x.warnings || [];
        var parts = x.components && x.components[recHorizon] || {};
        var details = '<details class="rec-detail"><summary>Yếu tố</summary><div class="rec-detail-body"><p><b>Điểm thành phần (bách phân vị 0–100)</b></p><dl>' +
          Object.keys(recLabels).map(function(key){
            var value = parts[key];
            return '<div><dt>' + esc(recLabels[key]) + '</dt><dd>' + (value === null || value === undefined ? 'Thiếu dữ liệu' : fmt(value, 1) + '/100') + '</dd></div>';
          }).join('') + '</dl><p>6 tháng: ' + (x.scores['6m'] === null ? 'Chưa đủ dữ liệu' : fmt(x.scores['6m'], 1) + '/100') +
          ' · P/B: ' + (m.pb === null ? '–' : fmt(m.pb, 2)) + ' · Biến động năm hóa: ' + (m.bien_dong_nam_pct === null ? '–' : fmt(m.bien_dong_nam_pct, 1) + '%') +
          ' · Sụt giảm tối đa 1 năm: ' + (m.sut_giam_toi_da_1n_pct === null ? '–' : fmt(m.sut_giam_toi_da_1n_pct, 1) + '%') +
          ' · Khối quỹ: ' + (m.so_quy === null ? '–' : m.so_quy) + ' quỹ mở có mã trong top 10, ' + (m.so_etf === null ? '–' : m.so_etf) + ' ETF có mã trong chỉ số tham chiếu (proxy)' +
          ' · Tỷ trọng quỹ bình quân: ' + (m.ty_trong_quy_tb_pct === null ? '–' : fmt(m.ty_trong_quy_tb_pct, 2) + '%') +
          ' · Cao nhất: ' + (m.ty_trong_quy_max_pct === null ? '–' : fmt(m.ty_trong_quy_max_pct, 2) + '%') +
          ' · Độ bao phủ điểm: ' + fmt(x.coverage[recHorizon], 0) + '%' +
          (x.ngay_gia ? ' · Giá đến ' + ngayVN(x.ngay_gia) : '') + (x.ky_tai_chinh ? ' · Kỳ tài chính ' + esc(x.ky_tai_chinh) : '') + '</p>' +
          (warnings.length ? '<p class="rec-warning-list"><b>Cảnh báo:</b> ' + warnings.map(esc).join(' · ') + '</p>' : '') +
          '</div></details>';
        var code = '<button type="button" class="rec-code" data-ma="' + esc(x.ma) + '">' + esc(x.ma) + '</button><span>' + esc(x.ten) + '</span><a href="#bctc=' + esc(x.ma) + '" class="rec-bctc" data-bctc="' + esc(x.ma) + '" title="Xem báo cáo tài chính của ' + esc(x.ma) + '">Báo cáo tài chính →</a>';
        return '<tr><td class="num">' + (i + 1) + '</td><td class="rec-company">' + code + '</td><td class="num"><b class="rec-score">' + fmt(x.scores[recHorizon], 1) + '</b><small>/100</small></td>' +
          '<td class="num">' + pct(m.loi_nhuan_3m_pct) + '</td><td class="num">' + pct(m.loi_nhuan_6m_pct) + '</td>' +
          '<td class="num">' + (m.roe_pct === null ? '–' : fmt(m.roe_pct, 1) + '%') + '</td><td class="num">' + (m.pe === null ? '–' : fmt(m.pe, 1) + 'x') + '</td>' +
          '<td class="num" title="Quỹ mở xuất hiện top 10 / ETF có mã trong chỉ số tham chiếu, không phải holdings ETF thực">' + (m.so_quy === null ? '–' : m.so_quy) + ' / ' + (m.so_etf === null ? '–' : m.so_etf) + '</td><td>' + (warnings.length ? '<span class="rec-warn" title="' + esc(warnings.join('; ')) + '">' + warnings.length + ' cảnh báo</span>' : '<span class="rec-ok">—</span>') + '</td><td>' + details + '</td></tr>';
      }).join('');
      $('#recTable').innerHTML = table + '</tbody></table>';
      $('#recTable').onclick = function(e){
        var button = e.target.closest('button[data-ma]');
        if(!button) return;
        var marketInput = $('[data-market-url]');
        if(window.KCN_moPopup) window.KCN_moPopup(button.getAttribute('data-ma'));
        else if(marketInput) location.href = marketInput.getAttribute('data-market-url') + '#ma=' + encodeURIComponent(button.getAttribute('data-ma'));
      };
    }
    function veRecBacktest(data){
      var body = $('#recBacktest');
      body.innerHTML = ['3m', '6m'].map(function(key){
        var x = data.backtest[key] || {};
        if(!x.so_ky) return '<article class="rec-bt-card"><h3>' + (key === '3m' ? '3 tháng' : '6 tháng') + '</h3><p>Chưa đủ dữ liệu lịch sử để tính.</p></article>';
        return '<article class="rec-bt-card"><h3>' + (key === '3m' ? '3 tháng' : '6 tháng') + '</h3><p class="muted-text">' + x.so_ky + ' kỳ · ' + ngayVN(x.tu) + ' – ' + ngayVN(x.den) + '</p>' +
          '<dl><div><dt>Top 10 mua theo động lượng</dt><dd>' + pct(x.top_tb_pct) + '</dd></div><div><dt>VN-Index</dt><dd>' + pct(x.vnindex_tb_pct) + '</dd></div>' +
          '<div><dt>Chênh lệch so với VN-Index</dt><dd>' + pct(x.top_chenh_vnindex_pct) + '</dd></div><div><dt>Kỳ top 10 vượt VN-Index</dt><dd>' + fmt(x.top_hon_vnindex_pct, 1) + '%</dd></div>' +
          '<div><dt>Top 10 điểm thấp</dt><dd>' + pct(x.day_duoi_tb_pct) + '</dd></div></dl></article>';
      }).join('');
    }
    load('co_phieu_khuyen_nghi.json').then(function(data){
      var excludedCount = Object.keys(data.ma_bi_loai || {}).reduce(function(total, key){ return total + (Number(data.ma_bi_loai[key]) || 0); }, 0);
      $('#recMeta').textContent = 'Giá đến ' + ngayVN(data.cap_nhat) + ' · ' + fmt(data.so_ma_phan_tich) + '/' + fmt(data.so_ma_trong_ro) + ' mã trong ' + esc(data.vung_loc || 'VN100') +
        ' · Danh mục quỹ đến ' + ngayVN(data.cap_nhat_quy) + ' · Loại khỏi lọc: ' + fmt(excludedCount) + ' mã. Nguồn: VCI, KBS và dữ liệu danh mục quỹ Kim Chỉ Nam.';
      $('#recSummary').innerHTML = '<span><b>' + fmt(data.so_ma_phan_tich) + '</b> mã đủ điều kiện</span><span><b>3–6 tháng</b> thời hạn lọc</span><span><b>' +
        fmt(data.trong_so.dong_luong) + '/' + fmt(data.trong_so.chat_luong) + '/' + fmt(data.trong_so.quy) + '/' + fmt(data.trong_so.dinh_gia) + '/' + fmt(data.trong_so.rui_ro) +
        '%</b> trọng số: giá / tài chính / quỹ / định giá / rủi ro</span>';
      veRecBang(data);
      veRecBacktest(data);
      $('#recHorizon').addEventListener('click', function(e){
        var b = e.target.closest('button[data-horizon]'); if(!b) return;
        recHorizon = b.getAttribute('data-horizon');
        $$('#recHorizon button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        veRecBang(data);
      });
      $('#recSide').addEventListener('click', function(e){
        var b = e.target.closest('button[data-side]'); if(!b) return;
        recSide = b.getAttribute('data-side');
        $$('#recSide button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        veRecBang(data);
      });
    }).catch(function(){
      $('#recMeta').textContent = 'Không tải được dữ liệu xếp hạng.';
      fail($('#recTable'), 'Chưa tải được bảng xếp hạng. Hãy thử tải lại trang sau.');
      fail($('#recBacktest'), 'Chưa tải được kết quả backtest.');
    });
  }

  // ---- Cổ Phiếu Khuyến Nghị: tab Báo cáo tài chính (dữ liệu assets/data/bctc/<MÃ>.json do scripts/bao_cao_tai_chinh.py tải từ Vietcap)
  var fsPane = $('#recPaneFs');
  if(fsPane){
    var fs = {ky: 'q', bc: 'kqkd', view: 'so', chinh: false, ma: null, data: null, ds: [], daMo: false};
    var FS_DT = {isa3: 'Doanh thu thuần', isb27: 'Thu nhập lãi thuần', isi103: 'Doanh thu phí bảo hiểm'};

    function fsSo(v, dv){ return v === null || v === undefined ? '–' : fmt(v, dv === 'VND' ? 0 : 1); }
    // tăng trưởng theo độ lớn so với cùng kỳ (quý: cách 4 kỳ, năm: cách 1 kỳ); khác dấu hoặc thiếu số thì không tính
    function fsYoY(arr, i, step){
      var cur = arr[i], prev = arr[i + step];
      if(cur === null || cur === undefined || prev === null || prev === undefined || cur === 0 || prev === 0 || (cur > 0) !== (prev > 0)) return null;
      return (cur / prev - 1) * 100;
    }
    function fsHang(bc, f){ return f ? (fs.data.bc[bc] || []).filter(function(r){ return r.f === f; })[0] : null; }
    function fsKy(){ return fs.ky === 'q' ? {per: fs.data.quy, key: 'q', step: 4} : {per: fs.data.nam, key: 'n', step: 1}; }

    function fsKpis(){
      var d = fs.data, k = fsKy(), tt = d.tt || {};
      var defs = [
        ['Doanh thu', 'kqkd', tt.dt, FS_DT[tt.dt] || 'Doanh thu'], ['Lợi nhuận sau thuế', 'kqkd', tt.lnst, 'Lợi nhuận sau thuế (công ty mẹ nếu có)'],
        ['Tổng tài sản', 'cdkt', tt.ts, 'Tổng tài sản cuối kỳ'], ['Vốn chủ sở hữu', 'cdkt', tt.vcsh, 'Vốn chủ sở hữu cuối kỳ'],
        ['Dòng tiền KD', 'lctt', tt.cfo, 'Lưu chuyển tiền thuần từ hoạt động kinh doanh']
      ];
      $('#fsKpis').innerHTML = defs.map(function(x){
        var r = fsHang(x[1], x[2]);
        if(!r) return '<article class="fs-kpi"><h3>' + esc(x[0]) + '</h3><p class="fs-kpi-v">–</p><p class="fs-kpi-s muted-text">Không có dữ liệu</p></article>';
        var arr = r[k.key], v = arr[0], g = fsYoY(arr, 0, k.step);
        var hist = arr.slice(0, 8).filter(function(z){ return z !== null && z !== undefined; }).reverse();
        return '<article class="fs-kpi" title="' + esc(x[3]) + '"><h3>' + esc(x[0]) + ' <span>· ' + esc(k.per[0].k) + '</span></h3><p class="fs-kpi-v' + (v < 0 ? ' neg' : '') + '">' + fsSo(v) + ' <small>tỷ</small></p>' +
          '<p class="fs-kpi-s ' + cls(g) + '">' + (g === null ? 'Chưa so sánh được' : pct(g, 1) + ' so cùng kỳ') + '</p>' +
          '<span class="fs-kpi-spark">' + sparkSvg(hist, 120, 28, g !== null && g < 0 ? css('--critical') : css('--good')) + '</span></article>';
      }).join('');
    }

    // biểu đồ cột nhóm: doanh thu và lợi nhuận sau thuế theo kỳ (cũ → mới)
    function fsBarSvg(labels, series){
      var W = 760, H = 230, pl = 52, pr = 8, pt = 22, pb = 28, all = [0];
      series.forEach(function(s){ s.v.forEach(function(x){ if(x !== null && x !== undefined) all.push(x); }); });
      var mx = Math.max.apply(null, all), mn = Math.min.apply(null, all);
      if(mx === mn) mx = mn + 1;
      var n = labels.length, gw = (W - pl - pr) / n, bw = Math.min(26, gw * 0.8 / series.length);
      function Y(v){ return pt + (mx - v) / (mx - mn) * (H - pt - pb); }
      var o = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Biểu đồ ' + esc(series.map(function(s){ return s.name; }).join(' và ')) + ' theo kỳ">';
      for(var i = 0; i <= 4; i++){
        var gv = mn + (mx - mn) * i / 4, gy = Y(gv);
        o += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + gy.toFixed(1) + '" y2="' + gy.toFixed(1) + '" class="fs-grid"/><text x="' + (pl - 6) + '" y="' + (gy + 4).toFixed(1) + '" text-anchor="end">' + fmt(gv, 0) + '</text>';
      }
      o += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '" class="fs-zero"/>';
      labels.forEach(function(lb, i){
        var x0 = pl + i * gw + (gw - bw * series.length) / 2;
        series.forEach(function(s, k){
          var v = s.v[i];
          if(v !== null && v !== undefined){
            var y = Y(Math.max(v, 0)), h = Math.max(1, Math.abs(Y(v) - Y(0)));
            o += '<rect x="' + (x0 + k * bw).toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + (bw - 2).toFixed(1) + '" height="' + h.toFixed(1) + '" rx="2" style="fill:' + s.color + '"><title>' + esc(s.name + ' ' + lb + ': ' + fmt(v, 1) + ' tỷ') + '</title></rect>';
          }
        });
        o += '<text x="' + (pl + i * gw + gw / 2).toFixed(1) + '" y="' + (H - 9) + '" text-anchor="middle">' + esc(lb) + '</text>';
      });
      series.forEach(function(s, k){
        o += '<rect x="' + (pl + k * 190) + '" y="4" width="10" height="10" rx="2" style="fill:' + s.color + '"/><text x="' + (pl + k * 190 + 15) + '" y="13">' + esc(s.name) + ' (tỷ đồng)</text>';
      });
      return o + '</svg>';
    }

    function fsChart(){
      var d = fs.data, k = fsKy(), tt = d.tt || {}, dt = fsHang('kqkd', tt.dt), ln = fsHang('kqkd', tt.lnst);
      var el = $('#fsChart');
      if(!dt && !ln){ el.innerHTML = ''; return; }
      var take = fs.ky === 'q' ? 12 : 6, per = k.per.slice(0, take).reverse();
      var pick = function(r){ return r ? r[k.key].slice(0, take).reverse() : []; };
      var series = [];
      if(dt) series.push({name: FS_DT[tt.dt] || 'Doanh thu', color: css('--accent'), v: pick(dt)});
      if(ln) series.push({name: 'Lợi nhuận sau thuế', color: css('--good'), v: pick(ln)});
      el.innerHTML = fsBarSvg(per.map(function(p){ return p.k; }), series);
    }

    function fsTable(){
      var d = fs.data, k = fsKy(), rows = (d.bc[fs.bc] || []).filter(function(r){ return !fs.chinh || r.c === 1; });
      var yoy = fs.view === 'yoy';
      var h = '<table class="data-table fs-table"><thead><tr><th scope="col" class="fs-sticky">Chỉ tiêu' + (yoy ? ' · % so cùng kỳ' : '') + '</th>' +
        k.per.map(function(p){ return '<th scope="col" class="num">' + esc(p.k) + (p.cb ? '<small title="Ngày công bố lần đầu (ước tính)' + (p.cn && p.cn !== p.cb ? '; cập nhật gần nhất ' + esc(ngayVN(p.cn)) : '') + '">CB ' + esc(ngayVN(p.cb).slice(0, 5) + '/' + p.cb.slice(2, 4)) + '</small>' : '') + '</th>'; }).join('') + '</tr></thead><tbody>';
      rows.forEach(function(r){
        h += '<tr class="fs-l' + Math.min(r.c || 1, 4) + (r.f ? '' : ' fs-group') + '"><th scope="row" class="fs-sticky">' + esc(r.t) + '</th>';
        k.per.forEach(function(p, i){
          if(!r.f){ h += '<td></td>'; return; }
          if(yoy){ var g = fsYoY(r[k.key], i, k.step); h += '<td class="num ' + cls(g) + '">' + (g === null ? '–' : pct(g, 1)) + '</td>'; return; }
          var v = r[k.key][i];
          h += '<td class="num' + (v < 0 ? ' neg' : '') + '">' + fsSo(v, r.dv) + '</td>';
        });
        h += '</tr>';
      });
      $('#fsTable').innerHTML = h + '</tbody></table>';
      var n = k.per[0];
      $('#fsNote').textContent = 'Đơn vị: tỷ đồng (dòng “trên cổ phiếu”: đồng). Cột mới nhất: ' + n.k + ', công bố lần đầu khoảng ' + ngayVN(n.cb) + (n.cn && n.cn !== n.cb ? ', số liệu cập nhật gần nhất ' + ngayVN(n.cn) : '') + '; báo cáo quý có thể được điều chỉnh sau khi soát xét hoặc kiểm toán. ' +
        (fs.bc === 'cdkt' ? 'Cân đối kế toán là số cuối kỳ. ' : fs.ky === 'q' ? 'Số phát sinh riêng từng quý. ' : '') + 'Nguồn: ' + (d.nguon || 'Vietcap') + ', cập nhật ' + ngayVN(d.cap_nhat) + '.';
    }

    function fsDoiChieu(){
      var kt = fs.data.kt, el = $('#fsKt');
      if(!kt){ el.innerHTML = ''; return; }
      var lech = kt.lech || [];
      if(lech.length){
        var ds = lech.map(function(c){
          return esc(c.ct + ' ' + c.nam + ': Vietcap ' + fmt(c.vietcap, 1) + ' / KBS ' + fmt(c.kbs, 1) + ' tỷ') +
            (c.goi_y === 'kbs_khop_quy' ? ' <i>(KBS khớp số tính từ các quý của Vietcap, nhiều khả năng số cả năm của Vietcap chưa chuẩn)</i>' : '');
        });
        el.innerHTML = '<div class="fs-kt-warn" role="alert"><b>Cảnh báo:</b> số liệu cả năm chưa thống nhất giữa hai nguồn, chưa xác định số nào đúng. Có thể do báo cáo được điều chỉnh hoặc lỗi nguồn: ' +
          ds.join('; ') + '. Hãy đối chiếu báo cáo gốc trước khi sử dụng.</div>';
      }else if(kt.so_sanh){
        el.innerHTML = '<div class="fs-kt-ok">✓ Đã đối chiếu ' + kt.so_sanh + ' số liệu cả năm với ' + esc(kt.nguon) + ': khớp (kiểm tra ngày ' + ngayVN(kt.ngay) + ').</div>';
      }else{
        el.innerHTML = '<div class="fs-kt-na">Chưa đối chiếu được với nguồn thứ hai.</div>';
      }
    }

    function fsVe(){
      var d = fs.data;
      $('#fsTitle').textContent = d.ma + ' · ' + d.ten;
      var m = d.quy && d.quy[0];
      $('#fsMeta').textContent = (d.loai === d.nganh ? d.loai : d.loai + ' · ' + d.nganh) + ' · Kỳ mới nhất ' + (m ? m.k + ' (công bố lần đầu ' + ngayVN(m.cb) + (m.cn && m.cn !== m.cb ? ', cập nhật ' + ngayVN(m.cn) : '') + ')' : '–') + ' · tỷ đồng · nguồn Vietcap';
      $('#fsBody').hidden = false;
      fsKpis(); fsChart(); fsTable(); fsDoiChieu();
    }

    function fsCsv(){
      var d = fs.data, k = fsKy(), rows = (d.bc[fs.bc] || []).filter(function(r){ return !fs.chinh || r.c === 1; });
      var q = function(s){ return '"' + String(s).replace(/"/g, '""') + '"'; };
      var lines = [[q('Chỉ tiêu')].concat(k.per.map(function(p){ return q(p.k); })).join(',')];
      rows.forEach(function(r){
        lines.push([q(r.t)].concat(k.per.map(function(p, i){
          if(!r.f) return '';
          if(fs.view === 'yoy'){ var g = fsYoY(r[k.key], i, k.step); return g === null ? '' : g.toFixed(1); }
          var v = r[k.key][i]; return v === null || v === undefined ? '' : v;
        })).join(','));
      });
      var blob = new Blob(['﻿' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'bctc_' + d.ma + '_' + fs.bc + '_' + (fs.ky === 'q' ? 'quy' : 'nam') + (fs.view === 'yoy' ? '_tang_truong' : '') + '.csv';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){ URL.revokeObjectURL(a.href); }, 2000);
    }

    function fsDatHash(ma, giu){
      try{ history.replaceState(null, '', location.pathname + location.search + (ma ? '#bctc=' + encodeURIComponent(ma) : (giu || ''))); }catch(e){}
    }
    function fsXem(ma, giuHash){
      ma = String(ma || '').trim().toUpperCase();
      if(!ma) return;
      if(fs.ds.length && !fs.ds.some(function(x){ return x.ma === ma; })){
        $('#fsMeta').textContent = 'Không có báo cáo tài chính cho mã “' + ma + '”. Chỉ có các mã trong danh sách gợi ý (VN100).';
        return;
      }
      $('#fsMeta').textContent = 'Đang tải báo cáo của ' + ma + '…';
      load('bctc/' + ma + '.json').then(function(d){
        fs.ma = ma; fs.data = d; $('#fsMa').value = ma;
        try{ localStorage.setItem('kcn_bctc_ma', ma); }catch(e){}
        if(!giuHash) fsDatHash(ma);
        fsVe();
      }).catch(function(){
        $('#fsMeta').textContent = 'Chưa tải được báo cáo của ' + ma + '. Hãy thử lại sau.';
        $('#fsBody').hidden = true;
      });
    }

    var TAB = {recPaneRank: 'recTabRank', recPaneFs: 'recTabFs', recPaneVal: 'recTabVal'};
    function chonTab(pane){
      Object.keys(TAB).forEach(function(p){ var on = p === pane; $('#' + p).hidden = !on; $('#' + TAB[p]).setAttribute('aria-selected', on ? 'true' : 'false'); });
    }
    function fsMo(ma){
      chonTab('recPaneFs');
      if(!fs.daMo){
        fs.daMo = true;
        load('bctc/muc_luc.json').then(function(m){
          fs.ds = m.ds || [];
          $('#fsList').innerHTML = fs.ds.map(function(x){ return '<option value="' + esc(x.ma) + '">' + esc(x.ten + ' · ' + x.nganh) + '</option>'; }).join('');
          var luu = ''; try{ luu = localStorage.getItem('kcn_bctc_ma') || ''; }catch(e){}
          var dau = ma || (fs.ds.some(function(x){ return x.ma === luu; }) ? luu : '') || (fs.ds.some(function(x){ return x.ma === 'FPT'; }) ? 'FPT' : (fs.ds[0] || {}).ma);
          $('#fsMeta').textContent = fs.ds.length + ' mã có báo cáo tài chính. Gõ mã hoặc chọn từ gợi ý.';
          if(dau) fsXem(dau);
        }).catch(function(){ $('#fsMeta').textContent = 'Chưa tải được danh sách báo cáo tài chính.'; });
      }else if(ma){ fsXem(ma); }
      else fsDatHash(fs.ma);
    }
    function fsDong(){
      chonTab('recPaneRank');
      fsDatHash('');
    }

    $('#recTabRank').addEventListener('click', fsDong);
    $('#recTabFs').addEventListener('click', function(){ fsMo(); });
    $('#recTabVal').addEventListener('click', function(){ valMo(); });
    $('#recTabRank').parentNode.addEventListener('keydown', function(e){
      if(e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var thu = ['recTabRank', 'recTabFs', 'recTabVal'], i = thu.indexOf(document.activeElement.id);
      if(i < 0) return;
      var j2 = Math.max(0, Math.min(2, i + (e.key === 'ArrowRight' ? 1 : -1)));
      [fsDong, function(){ fsMo(); }, valMo][j2](); $('#' + thu[j2]).focus();
    });
    $('#fsGo').addEventListener('click', function(){ fsXem($('#fsMa').value); });
    $('#fsMa').addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); fsXem(this.value); } });
    $('#fsMa').addEventListener('change', function(){ if(fs.ds.some(function(x){ return x.ma === this.value.trim().toUpperCase(); }, this)) fsXem(this.value); });
    function nhom(id, attr, key){
      $(id).addEventListener('click', function(e){
        var b = e.target.closest('button[' + attr + ']'); if(!b) return;
        fs[key] = b.getAttribute(attr);
        $$(id + ' button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        if(fs.data){ if(key === 'ky'){ fsKpis(); fsChart(); } fsTable(); }
      });
    }
    nhom('#fsKy', 'data-ky', 'ky'); nhom('#fsBc', 'data-bc', 'bc'); nhom('#fsView', 'data-view', 'view');
    $('#fsChinh').addEventListener('change', function(){ fs.chinh = this.checked; if(fs.data) fsTable(); });
    $('#fsCsv').addEventListener('click', function(){ if(fs.data) fsCsv(); });
    // ---- popup biểu đồ giá của một mã: dùng chung cho cả 3 tab (trang Thị trường có popup riêng nên chỉ định nghĩa ở đây khi trang chưa có)
    var cp = {chart: null, ma: null, range: 126, ve: null};
    function cpDong(){
      var m = $('#cpModal'); if(!m) return;
      m.hidden = true; document.body.classList.remove('cp-open'); cp.ma = null;
      if(cp.chart){ cp.chart.remove(); cp.chart = null; }
    }
    function cpKhung(){
      var m = $('#cpModal'); if(m) return m;
      m = document.createElement('div'); m.id = 'cpModal'; m.className = 'cp-modal'; m.hidden = true;
      m.innerHTML = '<div class="cp-box" role="dialog" aria-modal="true" aria-labelledby="cpTitle">' +
        '<div class="cp-head"><div><h3 id="cpTitle"></h3><p id="cpSub" class="muted-text"></p></div><button type="button" class="cp-x" id="cpClose" aria-label="Đóng">✕</button></div>' +
        '<div class="cp-stats" id="cpStats"></div>' +
        '<div class="cp-tools"><div class="seg" id="cpRange" role="group" aria-label="Khoảng thời gian">' +
        '<button type="button" data-n="63">3 tháng</button><button type="button" data-n="126" aria-pressed="true">6 tháng</button><button type="button" data-n="252">1 năm</button><button type="button" data-n="756">3 năm</button><button type="button" data-n="0">Tất cả</button></div>' +
        '<label class="fs-check"><input type="checkbox" id="cpMa" checked> Đường MA20/50/200</label><label class="fs-check"><input type="checkbox" id="cpVol" checked> Khối lượng</label></div>' +
        '<div id="cpChart" class="cp-chart"></div><div class="cp-links" id="cpLinks"></div></div>';
      document.body.appendChild(m);
      m.addEventListener('click', function(e){ if(e.target === m) cpDong(); });
      $('#cpClose').addEventListener('click', cpDong);
      $('#cpRange').addEventListener('click', function(e){
        var b = e.target.closest('button[data-n]'); if(!b) return;
        cp.range = Number(b.getAttribute('data-n'));
        $$('#cpRange button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        if(cp.chart) cpKhoang();
      });
      $('#cpMa').addEventListener('change', function(){ if(cp.ve) cp.ve(); });
      $('#cpVol').addEventListener('change', function(){ if(cp.ve) cp.ve(); });
      $('#cpLinks').addEventListener('click', function(e){ if(e.target.closest('a[data-bctc]')) cpDong(); });
      document.addEventListener('keydown', function(e){ if(e.key === 'Escape' && !m.hidden) cpDong(); });
      return m;
    }
    function cpKhoang(){
      var n = cp.n || 0, ts = cp.chart.timeScale();
      if(!cp.range || cp.range >= n) ts.fitContent(); else ts.setVisibleLogicalRange({from: n - cp.range, to: n + 3});
    }
    function cpMo(ma){
      ma = String(ma).toUpperCase();
      var m = cpKhung(); m.hidden = false; document.body.classList.add('cp-open');
      cp.ma = ma; cp.ve = null;
      if(cp.chart){ cp.chart.remove(); cp.chart = null; }
      $('#cpTitle').textContent = ma; $('#cpSub').textContent = 'Đang tải biểu đồ…'; $('#cpStats').innerHTML = ''; $('#cpChart').innerHTML = ''; $('#cpLinks').innerHTML = '';
      Promise.all([loadLwc(), load('cp/' + ma + '.json'), load('diem_tai_chinh.json').catch(function(){ return null; })]).then(function(res){
        if(cp.ma !== ma) return;                              // người dùng đã đóng hoặc mở mã khác
        var L = res[0], d = res[1], dg = res[2] && (res[2].ds || []).filter(function(x){ return x.ma === ma; })[0];
        var n = d.c.length, c = d.c, last = c[n - 1], rt = returns(d.d, c);
        $('#cpTitle').textContent = ma + ' · ' + d.ten;
        $('#cpSub').textContent = [d.nganh, d.san, 'giá đến ' + ngayVN(d.d[n - 1])].filter(Boolean).join(' · ');
        function o(nhan, v){ return '<div><span>' + nhan + '</span><b>' + v + '</b></div>'; }
        function ls(nhan, v){ return o(nhan, '<span class="' + cls(v) + '">' + pct(v, 1) + '</span>'); }
        var st = o('Giá đóng cửa', fmt(last) + ' đ') + ls('1 ngày', rt['1d']) + ls('1 tháng', rt['1m']) + ls('3 tháng', rt['3m']) + ls('6 tháng', rt['6m']) + ls('1 năm', rt['1y']);
        if(dg){
          var g = dg.ln_4q_truoc && dg.ln_4q_truoc > 0 && dg.ln_4q !== null ? (dg.ln_4q / dg.ln_4q_truoc - 1) * 100 : null;
          st += o('Điểm định giá', fmt(dg.diem, 1) + '<small>/100</small>') + o('P/E · P/B', (dg.pe === null ? '–' : fmt(dg.pe, 1) + 'x') + ' · ' + (dg.pb === null ? '–' : fmt(dg.pb, 2) + 'x')) +
            o('ROE', dg.f.roe === null ? '–' : fmt(dg.f.roe * 100, 1) + '%') + (g === null ? '' : ls('Lợi nhuận 4 quý so cùng kỳ', g));
        }
        $('#cpStats').innerHTML = st;
        var thi = $('[data-market-url]');
        $('#cpLinks').innerHTML = '<a href="#bctc=' + esc(ma) + '" data-bctc="' + esc(ma) + '">Báo cáo tài chính →</a>' +
          (thi ? '<a href="' + esc(thi.getAttribute('data-market-url')) + '#ma=' + encodeURIComponent(ma) + '">Phân tích kỹ thuật đầy đủ →</a>' : '');
        cp.n = n;
        cp.ve = function(){
          if(cp.chart){ cp.chart.remove(); cp.chart = null; }
          var box = $('#cpChart'); box.innerHTML = '';
          var up = css('--good'), down = css('--critical'), ink = css('--muted'), line = css('--border');
          var ch = cp.chart = L.createChart(box, {autoSize: true,
            layout: {background: {type: 'solid', color: 'transparent'}, textColor: ink, fontFamily: '"JetBrains Mono", monospace', fontSize: 11},
            grid: {vertLines: {color: line}, horzLines: {color: line}}, rightPriceScale: {borderColor: line, minimumWidth: 70}, timeScale: {borderColor: line, rightOffset: 3, minBarSpacing: 1},
            crosshair: {mode: 0},
            localization: {locale: 'vi-VN', priceFormatter: function(p){ return fmt(p); }, timeFormatter: function(t){ return ngayVN(typeof t === 'string' ? t : t.year + '-' + ('0' + t.month).slice(-2) + '-' + ('0' + t.day).slice(-2)); }}});
          var nen = ch.addSeries(L.CandlestickSeries, {upColor: up, downColor: down, borderVisible: false, wickUpColor: up, wickDownColor: down, priceFormat: {type: 'price', precision: 0, minMove: 10}});
          nen.setData(d.d.map(function(t, i){ return {time: t, open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i]}; }));
          var vol = $('#cpVol').checked;
          nen.priceScale().applyOptions({scaleMargins: {top: 0.06, bottom: vol ? 0.24 : 0.06}});
          if(vol){
            var hs = ch.addSeries(L.HistogramSeries, {priceFormat: {type: 'volume'}, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false});
            hs.priceScale().applyOptions({scaleMargins: {top: 0.82, bottom: 0}});
            hs.setData(d.d.map(function(t, i){ return {time: t, value: d.v[i], color: d.c[i] >= d.o[i] ? 'rgba(61,209,92,.4)' : 'rgba(255,107,97,.4)'}; }));
          }
          if($('#cpMa').checked){
            [[20, '#e08a1e'], [50, '#3b82c4'], [200, '#8e5bb5']].forEach(function(x){
              var s = ch.addSeries(L.LineSeries, {color: x[1], lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false});
              var arr = TA.sma(d.c, x[0]), pts = [];
              arr.forEach(function(v, i){ if(v !== null && v !== undefined && !isNaN(v)) pts.push({time: d.d[i], value: v}); });
              s.setData(pts);
            });
          }
          cpKhoang();
        };
        cp.ve();
      }).catch(function(){ if(cp.ma === ma) $('#cpSub').textContent = 'Không tải được dữ liệu giá của ' + ma + '. Hãy thử lại sau.'; });
    }
    if(!window.KCN_moPopup) window.KCN_moPopup = cpMo;

    // ---- tab Định giá theo BCTC: điểm E/P + B/P từ assets/data/diem_tai_chinh.json (scripts/diem_tai_chinh.py) và kết quả backtest (scripts/backtest_tai_chinh.py)
    var val = {side: 'cao', data: null, daMo: false};
    function valMo(){
      chonTab('recPaneVal');
      fsDatHash('', '#dinh-gia');
      if(val.daMo) return;
      val.daMo = true;
      load('diem_tai_chinh.json').then(function(d){ val.data = d; valVe(); }).catch(function(){
        $('#valMeta').textContent = 'Không tải được dữ liệu định giá.';
        fail($('#valTable'), 'Chưa tải được bảng điểm. Hãy thử tải lại trang sau.'); fail($('#valBt'), 'Chưa tải được kết quả backtest.');
      });
    }
    function valBang(){
      var d = val.data, ds = d.ds || [];
      var ds10 = val.side === 'cao' ? ds.slice(0, 10) : ds.slice(-10).reverse();
      $('#valTitle').textContent = val.side === 'cao' ? 'Nhóm điểm cao nhất: rẻ nhất so với báo cáo tài chính' : 'Nhóm điểm thấp nhất: đắt nhất so với báo cáo tài chính';
      var h = '<table class="data-table rec-table"><thead><tr><th scope="col" class="num">#</th><th scope="col">Mã / doanh nghiệp</th><th scope="col" class="num">Điểm</th>' +
        '<th scope="col" class="num" title="Giá / lợi nhuận sau thuế 4 quý">P/E</th><th scope="col" class="num" title="Vốn hóa / vốn chủ sở hữu">P/B</th><th scope="col" class="num">ROE</th>' +
        '<th scope="col" class="num" title="Lợi nhuận sau thuế 4 quý gần nhất so với 4 quý cùng kỳ năm trước">Lợi nhuận 4 quý</th><th scope="col" class="num">So cùng kỳ</th></tr></thead><tbody>';
      ds10.forEach(function(r, i){
        var g = r.ln_4q_truoc && r.ln_4q_truoc > 0 && r.ln_4q !== null ? (r.ln_4q / r.ln_4q_truoc - 1) * 100 : null;
        var dot = g !== null && g > 150 ? ' <span class="val-flag" title="Lợi nhuận tăng đột biến, có thể do khoản thu một lần làm cổ phiếu trông rẻ hơn thực tế">đột biến?</span>' : '';
        h += '<tr><td class="num">' + (val.side === 'cao' ? i + 1 : ds.length - i) + '</td><td class="rec-company"><button type="button" class="rec-code" data-ma="' + esc(r.ma) + '">' + esc(r.ma) + '</button>' +
          (r.canh_bao_du_lieu ? ' <span class="val-warn" title="Hai nguồn báo cáo ghi số cả năm khác nhau, hãy đối chiếu báo cáo gốc">⚠</span>' : '') + '<span>' + esc(r.ten) + '</span>' +
          '<a href="#bctc=' + esc(r.ma) + '" class="rec-bctc" data-bctc="' + esc(r.ma) + '">Báo cáo tài chính →</a></td>' +
          '<td class="num"><b class="rec-score">' + fmt(r.diem, 1) + '</b><small>/100</small></td>' +
          '<td class="num">' + (r.pe === null ? '–' : fmt(r.pe, 1) + 'x') + '</td><td class="num">' + (r.pb === null ? '–' : fmt(r.pb, 2) + 'x') + '</td>' +
          '<td class="num">' + (r.f.roe === null ? '–' : fmt(r.f.roe * 100, 1) + '%') + '</td><td class="num">' + (r.ln_4q === null ? '–' : fmt(r.ln_4q, 0) + ' tỷ') + '</td>' +
          '<td class="num ' + cls(g) + '">' + (g === null ? (r.ln_4q > 0 && r.ln_4q_truoc <= 0 ? 'lỗ → lãi' : '–') : pct(g, 0)) + dot + '</td></tr>';
      });
      $('#valTable').innerHTML = h + '</tbody></table>';
      $('#valTable').onclick = function(e){
        var b = e.target.closest('button[data-ma]');
        if(b && window.KCN_moPopup) window.KCN_moPopup(b.getAttribute('data-ma'));
      };
    }
    function valCard(nhan, r){
      if(!r) return '';
      var mx = Math.max.apply(null, r.nhom.map(function(v){ return Math.abs(v); })) || 1;
      var bars = r.nhom.map(function(v, i){
        return '<div class="val-bar"><span class="val-bar-l">' + (i === 0 ? 'Điểm thấp nhất' : i === 4 ? 'Điểm cao nhất' : 'Nhóm ' + (i + 1)) + '</span><span class="val-bar-t"><i class="' + (v < 0 ? 'neg' : '') + '" style="width:' + (Math.abs(v) / mx * 100).toFixed(0) + '%"></i></span><b>' + pct(v * 100, 1) + '</b></div>';
      }).join('');
      return '<article class="rec-bt-card"><h3>Giữ ' + esc(nhan) + '</h3><p class="muted-text" style="margin:0 0 6px">Lợi nhuận giá trung bình mỗi nhóm 20 mã</p>' + bars +
        '<dl class="val-dl"><div><dt>Chênh nhóm cao − nhóm thấp</dt><dd>' + pct(r.q5_tru_q1 * 100, 1) + '</dd></div><div><dt>Nhóm cao hơn nhóm thấp</dt><dd>' + fmt(r.q5_hon_q1 * 100, 0) + '% số kỳ</dd></div>' +
        '<div><dt>Tương quan hạng (IC)</dt><dd>' + (r.ic > 0 ? '+' : '') + fmt(r.ic, 3) + ' · t = ' + fmt(r.ic_t, 1) + '</dd></div><div><dt>Số kỳ độc lập</dt><dd>' + r.so_ky + '</dd></div></dl></article>';
    }
    function valVe(){
      var d = val.data, bt = d.backtest;
      $('#valMeta').textContent = 'Giá đến ' + ngayVN(d.gia_den) + ' · báo cáo tài chính đến ' + (d.ds[0] ? d.ds[0].ky : '–') + ' · ' + fmt(d.so_ma) + ' cổ phiếu VN100. Nguồn: Vietcap (giá, báo cáo), KBS (đối chiếu).';
      valBang();
      $('#valNote').textContent = 'Điểm là thứ hạng tương đối trong nhóm, không phải xác suất sinh lời. Lợi nhuận đột biến một lần làm cổ phiếu trông rẻ hơn thực tế: hãy xem cột “So cùng kỳ” và bấm “Báo cáo tài chính” để kiểm tra nguồn gốc lợi nhuận.';
      $('#valSide').addEventListener('click', function(e){
        var b = e.target.closest('button[data-side]'); if(!b) return;
        val.side = b.getAttribute('data-side');
        $$('#valSide button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        valBang();
      });
      if(!bt || !bt.tre_30){ fail($('#valBt'), 'Chưa có kết quả backtest.'); return; }
      var b30 = bt.tre_30;
      $('#valBtMeta').textContent = 'Mỗi cuối tháng từ ' + ngayVN(bt.thoi_gian.tu) + ' đến ' + ngayVN(bt.thoi_gian.den) + ': xếp các cổ phiếu VN100 hiện tại (' + bt.thoi_gian.so_ma + ' mã có đủ dữ liệu, mỗi kỳ khoảng 90 mã) chỉ bằng báo cáo đã công bố tại thời điểm đó, vào lệnh ở phiên kế tiếp, chia 5 nhóm đều trọng số. Chưa tính phí, thuế, trượt giá.';
      $('#valBt').innerHTML = valCard('1 tháng', b30['21']) + valCard('3 tháng', b30['63']) + valCard('6 tháng', b30['126']);
      var rows = Object.keys(bt.yeu_to).map(function(k){
        var r = bt.yeu_to[k], tinh = (d.trong_so && d.trong_so[k] !== undefined), cungDau = r.ic > 0 && r.ic_nua_dau > 0 && r.ic_nua_sau > 0;
        var kl = cungDau && r.ic_t >= 2.7 ? '<span class="up"><b>Có tác dụng</b></span>' : cungDau && r.ic_t >= 2 ? '<b>Có dấu hiệu</b>' : '<span class="muted-text">Chưa chứng minh được</span>';
        return '<tr><td>' + esc(d.nhan[k] || k) + '</td><td>' + (tinh ? '<b>Tính vào điểm</b>' : '<span class="muted-text">Chỉ tham khảo</span>') + '</td><td class="num">' + (r.ic > 0 ? '+' : '') + fmt(r.ic, 3) + '</td><td class="num">' + fmt(r.ic_t, 1) + '</td>' +
          '<td class="num">' + (r.ic_nua_dau > 0 ? '+' : '') + fmt(r.ic_nua_dau, 3) + '</td><td class="num">' + (r.ic_nua_sau > 0 ? '+' : '') + fmt(r.ic_nua_sau, 3) + '</td><td>' + kl + '</td></tr>';
      }).join('');
      $('#valFactors').innerHTML = '<table class="data-table"><thead><tr><th scope="col">Yếu tố từ báo cáo tài chính</th><th scope="col">Vai trò</th><th scope="col" class="num" title="Hệ số tương quan hạng giữa yếu tố và lợi nhuận 3 tháng sau">IC 3 tháng</th><th scope="col" class="num" title="Thống kê t trên các kỳ không chồng lấn; từ 2 trở lên mới đáng tin hơn ngẫu nhiên">t</th><th scope="col" class="num">IC nửa đầu</th><th scope="col" class="num">IC nửa sau</th><th scope="col">Kết luận</th></tr></thead><tbody>' + rows + '</tbody></table>' +
        '<p class="table-note">“Có tác dụng” = IC dương ở cả hai nửa giai đoạn và t từ 2,7 trở lên (ngưỡng đã nâng lên vì thử 8 yếu tố cùng lúc nên dễ có kết quả đẹp do may rủi); “Có dấu hiệu” = t từ 2 đến dưới 2,7. ' +
        'Mô hình giữ hai yếu tố định giá vì E/P đạt mức cao nhất, còn B/P là yếu tố định giá kinh điển có cơ sở lý luận từ trước. Tăng tốc lợi nhuận có dấu hiệu nhưng IC nhỏ nên chưa đưa vào điểm. Tăng trưởng lợi nhuận, doanh thu, ROE và dòng tiền chưa chứng minh được tác dụng.</p>';
    }
    // liên kết trực tiếp: …/co-phieu-khuyen-nghi/#bctc=FPT mở thẳng tab báo cáo tài chính
    var hm = /^#bctc(?:=([A-Za-z0-9]{1,12}))?$/.exec(location.hash);
    if(hm) fsMo(hm[1] ? hm[1].toUpperCase() : '');
    else if(location.hash === '#dinh-gia') valMo();
    // đổi #bctc=… trên thanh địa chỉ (dán liên kết, nút Quay lại) thì cập nhật theo
    window.addEventListener('hashchange', function(){
      var h = /^#bctc(?:=([A-Za-z0-9]{1,12}))?$/.exec(location.hash);
      if(h){ var m = h[1] ? h[1].toUpperCase() : ''; if($('#recPaneFs').hidden || (m && m !== fs.ma)) fsMo(m); }
      else if(location.hash === '#dinh-gia'){ if($('#recPaneVal').hidden) valMo(); }
      else if(!$('#recPaneFs').hidden || !$('#recPaneVal').hidden) fsDong();
    });
    // bấm nút “Xem báo cáo tài chính” (data-bctc) ở bất kỳ đâu trên trang
    document.addEventListener('click', function(e){
      var b = e.target.closest('[data-bctc]'); if(!b) return;
      e.preventDefault(); fsMo(b.getAttribute('data-bctc')); window.scrollTo({top: $('#recTabFs').getBoundingClientRect().top + window.pageYOffset - 80, behavior: 'smooth'});
    });
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
      chartBox.innerHTML = '';
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

      var tieuDe = $('#smFund').previousElementSibling.firstChild;
      if(d.loai === 'etf'){
        tieuDe.textContent = 'Thông tin quỹ ';
        $('#smKy').textContent = '';
        $('#smFund').innerHTML =
          '<div><dt>Loại</dt><dd>Quỹ ETF</dd></div>' +
          '<div><dt>CCQ đang lưu hành</dt><dd>' + (d.co_phieu_niem_yet ? fmt(d.co_phieu_niem_yet) : '–') + '</dd></div>' +
          '<div><dt>Giá trị theo giá thị trường</dt><dd>' + (d.co_phieu_niem_yet ? fmt(c * d.co_phieu_niem_yet / 1e9, 0) + ' tỷ' : '–') + '</dd></div>' +
          '<div><dt></dt><dd><a class="sm-link" href="' + BASE + '/etf/chi-tiet/?ma=' + esc(d.ma) + '">Xem trang chi tiết quỹ →</a></dd></div>';
        return;
      }
      tieuDe.textContent = 'Chỉ số cơ bản ';
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
      capNhatSao();
      $('#smName').textContent = row ? row.ten : '';
      $('#smSector').textContent = row ? row.nganh : '';
      // xoá ngay nội dung của mã trước, không để biểu đồ/giá cũ nằm lại trong lúc chờ tải
      if(chart){ chart.remove(); chart = null; }
      data = null;
      chartBox.innerHTML = '<div class="sm-loading"><span class="sm-spin"></span>Đang tải biểu đồ ' + esc(maCk) + '…</div>';
      legend.textContent = '';
      var coGia = row && row.gia !== null && row.gia !== undefined;
      $('#smPrice').textContent = coGia ? fmt(row.gia) : '–';
      var chg0 = $('#smChg');
      chg0.className = 'sm-chg ' + (coGia ? cls(row.thay_doi) : '');
      chg0.textContent = coGia ? pct(row.thay_doi) : '';
      $('#smTime').textContent = '';
      ['#smSession', '#smFund'].forEach(function(id){ $(id).innerHTML = '<div class="sm-skel"></div><div class="sm-skel"></div><div class="sm-skel"></div>'; });
      $('#smWeek52').innerHTML = '<div class="sm-skel"></div>';
      $('#smPerf').innerHTML = '';
      $('#smKy').textContent = '';
      try{ history.replaceState(null, '', '#ma=' + maCk + '&cb=' + active.join(',')); }catch(e){}
      dialog.focus();
      Promise.all([loadLwc(), load('cp/' + maCk + '.json')]).then(function(res){
        if(current !== maCk) return;
        L = res[0]; data = res[1];
        $('#smName').textContent = data.ten;
        $('#smSector').textContent = data.nganh;
        compute();
        side();
        rebuild();
        prefetchNeighbors();
      }).catch(function(){
        if(current !== maCk) return;
        chartBox.innerHTML = '<div class="sm-loading">Chưa tải được dữ liệu của ' + esc(maCk) + '. Bấm lại vào mã để thử lại.</div>';
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

    function prefetchNeighbors(){
      var list = getList(), i = -1;
      list.forEach(function(x, j){ if(x.ma === current) i = j; });
      if(i < 0) return;
      [-1, 1].forEach(function(k){
        var nb = list[(i + k + list.length) % list.length];
        if(nb) load('cp/' + nb.ma + '.json').catch(function(){});
      });
    }

    function step(k){
      var list = getList(), i = -1;
      list.forEach(function(x, j){ if(x.ma === current) i = j; });
      if(i < 0 || !list.length) return;
      var nx = list[(i + k + list.length) % list.length];
      open(nx.ma, nx);
    }

    function capNhatSao(){
      var b = $('#smStar'); if(!b || !current) return;
      var on = docSao().indexOf(current) > -1;
      b.textContent = on ? '★' : '☆';
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
      b.setAttribute('aria-label', on ? 'Bỏ ghim khỏi danh sách của tôi' : 'Ghim vào danh sách của tôi');
    }
    if($('#smStar')){
      $('#smStar').addEventListener('click', function(){ if(current){ doiSao(current); } });
      document.addEventListener('kcn-sao', capNhatSao);
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

    function prefetch(maCk){
      loadLwc().catch(function(){});
      load('cp/' + maCk + '.json').catch(function(){});
    }

    return {open: open, setActive: setActive, prefetch: prefetch};
  }

  // =====================================================================
  // TRANG THỊ TRƯỜNG
  // =====================================================================

  // ---------- danh sách mã ghim (★), lưu trên trình duyệt
  function docSao(){
    try{ var v = JSON.parse(localStorage.getItem('kcn-sao')); return Array.isArray(v) ? v : []; }catch(e){ return []; }
  }
  function doiSao(ma){
    var ds = docSao(), i = ds.indexOf(ma);
    if(i > -1) ds.splice(i, 1); else ds.push(ma);
    try{ localStorage.setItem('kcn-sao', JSON.stringify(ds)); }catch(e){}
    document.dispatchEvent(new CustomEvent('kcn-sao'));
    return i === -1;
  }

  // ---------- trạng thái phiên theo giờ Việt Nam
  function trangThaiPhien(){
    var n = bayGioVN(), thu = n.getDay(), p = n.getHours() * 60 + n.getMinutes();
    if(thu === 0 || thu === 6) return ['nghi', 'Nghỉ cuối tuần'];
    if(p < 9 * 60) return ['cho', 'Chưa mở cửa'];
    if(p < 9 * 60 + 15) return ['ato', 'Phiên ATO'];
    if(p < 11 * 60 + 30) return ['lt', 'Khớp lệnh liên tục'];
    if(p < 13 * 60) return ['nghi', 'Nghỉ trưa'];
    if(p < 14 * 60 + 30) return ['lt', 'Khớp lệnh liên tục'];
    if(p < 14 * 60 + 45) return ['ato', 'Phiên ATC'];
    return ['dong', 'Đã đóng cửa'];
  }

  // màu giá theo quy ước bảng giá Việt Nam
  function mauGia(s){
    if(s.tran && s.gia >= s.tran) return 'c-tran';
    if(s.san && s.gia <= s.san) return 'c-san';
    if(s.tham_chieu && s.gia === s.tham_chieu) return 'c-tc';
    return cls(s.thay_doi);
  }
  function ty(dong, dg){ return dong === null || dong === undefined ? '–' : fmt(dong / 1e9, dg === undefined ? 1 : dg); }

  // ---------- bản đồ nhiệt: thuật toán squarified treemap
  function treemap(items, x, y, w, h){
    var out = [], rest = items.slice();
    function worst(row, side){
      var sum = 0, mx = 0, mn = Infinity;
      row.forEach(function(r){ sum += r.area; if(r.area > mx) mx = r.area; if(r.area < mn) mn = r.area; });
      return Math.max(side * side * mx / (sum * sum), (sum * sum) / (side * side * mn));
    }
    while(rest.length){
      var side = Math.min(w, h), row = [rest[0]], i = 1;
      while(i < rest.length && worst(row.concat(rest[i]), side) <= worst(row, side)){ row.push(rest[i]); i++; }
      var sum = row.reduce(function(a, r){ return a + r.area; }, 0);
      if(w >= h){
        var cw = sum / h, yy = y;
        row.forEach(function(r){ var rh = r.area / cw; out.push({it: r.it, x: x, y: yy, w: cw, h: rh}); yy += rh; });
        x += cw; w -= cw;
      }else{
        var rh2 = sum / w, xx = x;
        row.forEach(function(r){ var rw = r.area / rh2; out.push({it: r.it, x: xx, y: y, w: rw, h: rh2}); xx += rw; });
        y += rh2; h -= rh2;
      }
      rest = rest.slice(row.length);
    }
    return out;
  }
  function tron(a, b, t){
    var x = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)];
    var y = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)];
    return 'rgb(' + x.map(function(v, i){ return Math.round(v + (y[i] - v) * t); }).join(',') + ')';
  }
  function mauNhiet(s){
    if(s.tran && s.gia >= s.tran) return '#8A4FD6';
    if(s.san && s.gia <= s.san) return '#2AA9C9';
    var p = s.thay_doi || 0, t = Math.min(Math.abs(p) / 3, 1);
    if(Math.abs(p) < 0.005) return '#3A4770';
    return p > 0 ? tron('#2E4A5E', '#25A653', 0.25 + t * 0.75) : tron('#4A3550', '#B83B3B', 0.25 + t * 0.75);
  }

  var mkt = $('#mktChart');
  if(mkt){
    var M = {cs: null, cp: null, rows: [], ro: 'VN30', current: 'VNINDEX', months: 3, sortKey: 'ma', dir: 1, filter: '', tab: 'all', top: 'tang', shown: [], cu: {}};
    try{ var roLuu = localStorage.getItem('kcn-ro'); if(['VN100', 'FTSE27', 'FTSE6'].indexOf(roLuu) > -1) M.ro = roLuu; }catch(e){}
    function trongRo(){ return M.rows.filter(function(s){ return !s.ro || s.ro.indexOf(M.ro) > -1; }); }
    var modal = StockModal(function(){ return M.shown.length ? M.shown : M.rows; });
    var chart = LineChart(mkt, {label: 'Diễn biến chỉ số', area: true, yDigits: 0});
    var body = $('#wlBody');

    function rowCua(ma){ return M.rows.filter(function(x){ return x.ma === ma; })[0]; }
    function moRow(ma){ modal.open(ma, rowCua(ma)); }

    function phien(){
      var t = trangThaiPhien(), el = $('#mktPhien');
      el.className = 'phien-badge ph-' + t[0];
      $('b', el).textContent = t[1];
    }

    function the(){
      var keys = ['VNINDEX', 'VN30', 'HNXINDEX', 'UPCOMINDEX'].filter(function(k){ return M.cs[k]; });
      if(keys.indexOf(M.current) < 0) M.current = keys[0];
      $('#mktCards').innerHTML = keys.map(function(k){
        var s = M.cs[k], n = s.c.length, ch = s.c[n - 1] - s.c[n - 2], p = (s.c[n - 1] / s.c[n - 2] - 1) * 100;
        return '<button class="index-card" type="button" data-k="' + k + '" aria-pressed="' + (k === M.current) + '">' +
          '<p class="name">' + esc(s.ten) + '</p><p class="val tabular">' + fmt(s.c[n - 1], 2) + '</p>' +
          '<span class="chg ' + cls(ch) + '">' + (ch >= 0 ? '▲ +' : '▼ −') + fmt(Math.abs(ch), 2) + ' (' + pct(p).replace(/^[+−]/, '') + ')</span></button>';
      }).join('');
    }

    function toMauDuong(down){
      mkt.querySelectorAll('svg path').forEach(function(p, i){
        var st = p.getAttribute('stroke');
        if(st && st !== '#3DD15C' && st !== '#FF6B61') return; // giữ màu đường tham chiếu
        if(st) p.setAttribute('stroke', down ? '#FF6B61' : '#3DD15C');
        else p.setAttribute('fill', down ? '#FF6B61' : '#3DD15C');
      });
    }
    function veTrongNgay(){
      load('chi_so_ngay.json').then(function(nd){
        var x = nd.chi_so && nd.chi_so[M.current], s = M.cs[M.current];
        if(!x || !x.t.length){ $('#mktRet').innerHTML = '<span>Chưa có dữ liệu trong ngày của chỉ số này.</span>'; return; }
        var tc = x.tham_chieu || x.c[0];
        chart.render([
          {name: s.ten + ' ' + ngayVN(nd.ngay), color: '#3DD15C', d: x.t, c: x.c},
          {name: 'Tham chiếu', color: '#F0B429', d: x.t, c: x.t.map(function(){ return tc; })}
        ], 0, false);
        var cuoi = x.c[x.c.length - 1], ch = cuoi - tc;
        toMauDuong(ch < 0);
        var thap = Math.min.apply(null, x.c), cao = Math.max.apply(null, x.c);
        $('#mktRet').innerHTML = '<span>Phiên ' + ngayVN(nd.ngay) + ' <b class="' + cls(ch) + '">' + (ch >= 0 ? '+' : '−') + fmt(Math.abs(ch), 2) + ' (' + pct(ch / tc * 100) + ')</b></span>' +
          '<span>Cao nhất <b>' + fmt(cao, 2) + '</b></span><span>Thấp nhất <b>' + fmt(thap, 2) + '</b></span><span>Lúc <b>' + esc(x.t[x.t.length - 1]) + '</b></span>';
      }).catch(function(){ $('#mktRet').innerHTML = '<span>Chưa có dữ liệu trong ngày.</span>'; });
    }
    function veChiSo(){
      if(M.months === -1){ veTrongNgay(); return; }
      var s = M.cs[M.current];
      chart.render([{name: s.ten, color: '#3DD15C', d: s.d, c: s.c}], M.months, false);
      var leg = mkt.querySelector('.lc-legend b');
      toMauDuong(leg && leg.classList.contains('down'));
      var ret = returns(s.d, s.c);
      $('#mktRet').innerHTML = KY.map(function(k){
        return '<span>' + k[1] + ' <b class="' + cls(ret[k[0]]) + '">' + pct(ret[k[0]]) + '</b></span>';
      }).join('');
    }

    function banDoNhiet(){
      var box = $('#mktHeat'), W = box.clientWidth, H = box.clientHeight;
      if(!W || !H) return;
      var ds = trongRo().filter(function(s){ return s.von_hoa > 0; }).sort(function(a, b){ return b.von_hoa - a.von_hoa; });
      var tong = ds.reduce(function(a, s){ return a + s.von_hoa; }, 0);
      var rects = treemap(ds.map(function(s){ return {it: s, area: s.von_hoa / tong * W * H}; }), 0, 0, W, H);
      box.innerHTML = rects.map(function(r){
        var s = r.it, nho = r.w < 44 || r.h < 30, rat = r.w < 30 || r.h < 18;
        return '<button type="button" role="listitem" class="hm-tile' + (nho ? ' hm-sm' : '') + '" data-ma="' + esc(s.ma) + '" ' +
          'style="left:' + r.x.toFixed(1) + 'px;top:' + r.y.toFixed(1) + 'px;width:' + r.w.toFixed(1) + 'px;height:' + r.h.toFixed(1) + 'px;background:' + mauNhiet(s) + '" ' +
          'title="' + esc(s.ma + ' · ' + s.ten + ' · ' + fmt(s.gia) + ' đ · ' + pct(s.thay_doi) + ' · vốn hoá ' + fmt(s.von_hoa / 1e12, 1) + ' nghìn tỷ') + '" ' +
          'aria-label="' + esc(s.ma + ' ' + pct(s.thay_doi)) + '">' +
          (rat ? '' : '<b>' + esc(s.ma) + '</b>' + (nho ? '' : '<span>' + pct(s.thay_doi) + '</span>')) + '</button>';
      }).join('');
    }

    function doRong(){
      var t = 0, g = 0, d = 0, tr = 0, sa = 0, gt = 0;
      var ro = trongRo();
      ro.forEach(function(s){
        var c = mauGia(s);
        if(c === 'c-tran'){ tr++; t++; } else if(c === 'c-san'){ sa++; g++; }
        else if(s.thay_doi > 0) t++; else if(s.thay_doi < 0) g++; else d++;
        gt += s.gtgd || 0;
      });
      var n = ro.length || 1;
      $('#mktBreadth').innerHTML =
        '<div class="br-bar" role="img" aria-label="' + t + ' mã tăng, ' + d + ' đứng giá, ' + g + ' mã giảm">' +
          '<i class="up-bg" style="width:' + (t / n * 100) + '%"></i><i class="flat-bg" style="width:' + (d / n * 100) + '%"></i><i class="down-bg" style="width:' + (g / n * 100) + '%"></i></div>' +
        '<div class="br-nums">' +
          '<span><b class="up">' + t + '</b> tăng' + (tr ? ' <small class="c-tran">(' + tr + ' trần)</small>' : '') + '</span>' +
          '<span><b class="c-tc">' + d + '</b> đứng</span>' +
          '<span><b class="down">' + g + '</b> giảm' + (sa ? ' <small class="c-san">(' + sa + ' sàn)</small>' : '') + '</span></div>' +
        '<p class="br-note">Tổng giá trị giao dịch ' + M.ro + ': <b>' + ty(gt, 0) + ' tỷ</b></p>';
    }

    function noiBat(){
      var ds = trongRo(), k = M.top;
      if(k === 'tang') ds.sort(function(a, b){ return b.thay_doi - a.thay_doi; });
      else if(k === 'giam') ds.sort(function(a, b){ return a.thay_doi - b.thay_doi; });
      else if(k === 'kl') ds.sort(function(a, b){ return b.khoi_luong - a.khoi_luong; });
      else ds.sort(function(a, b){ return (b.gtgd || 0) - (a.gtgd || 0); });
      ds = ds.slice(0, 5);
      var mx = Math.max.apply(null, ds.map(function(s){ return k === 'kl' ? s.khoi_luong : k === 'gtgd' ? (s.gtgd || 0) : Math.abs(s.thay_doi); })) || 1;
      $('#mktTop').innerHTML = ds.map(function(s, i){
        var v = k === 'kl' ? s.khoi_luong : k === 'gtgd' ? (s.gtgd || 0) : Math.abs(s.thay_doi);
        var nhan = k === 'kl' ? fmt(s.khoi_luong / 1e6, 2) + ' tr' : k === 'gtgd' ? ty(s.gtgd) + ' tỷ' : pct(s.thay_doi);
        return '<li><button type="button" data-ma="' + esc(s.ma) + '"><span class="tl-i">' + (i + 1) + '</span><b>' + esc(s.ma) + '</b>' +
          '<span class="tl-p ' + mauGia(s) + '">' + fmt(s.gia) + '</span>' +
          '<span class="tl-bar"><i class="' + (k === 'giam' ? 'down-bg' : k === 'tang' ? 'up-bg' : 'acc-bg') + '" style="width:' + (v / mx * 100) + '%"></i></span>' +
          '<span class="tl-v ' + (k === 'tang' || k === 'giam' ? cls(s.thay_doi) : '') + '">' + nhan + '</span></button></li>';
      }).join('');
    }

    function khoiNgoai(){
      var mua = 0, ban = 0, co = false;
      var ds = trongRo().map(function(s){
        if(s.nn_mua !== null && s.nn_mua !== undefined){ co = true; mua += s.nn_mua; ban += s.nn_ban || 0; }
        return {s: s, r: (s.nn_mua || 0) - (s.nn_ban || 0)};
      });
      if(!co){ $('#mktForeign').innerHTML = '<p class="br-note">Chưa có số liệu khối ngoại.</p>'; return; }
      var rong = mua - ban;
      var muaR = ds.filter(function(x){ return x.r > 0; }).sort(function(a, b){ return b.r - a.r; }).slice(0, 3);
      var banR = ds.filter(function(x){ return x.r < 0; }).sort(function(a, b){ return a.r - b.r; }).slice(0, 3);
      var mx = Math.max.apply(null, muaR.concat(banR).map(function(x){ return Math.abs(x.r); })) || 1;
      function dong(x){
        return '<li><button type="button" data-ma="' + esc(x.s.ma) + '"><b>' + esc(x.s.ma) + '</b>' +
          '<span class="tl-bar"><i class="' + (x.r > 0 ? 'up-bg' : 'down-bg') + '" style="width:' + (Math.abs(x.r) / mx * 100) + '%"></i></span>' +
          '<span class="tl-v ' + cls(x.r) + '">' + (x.r > 0 ? '+' : '−') + ty(Math.abs(x.r)) + '</span></button></li>';
      }
      $('#mktForeign').innerHTML =
        '<div class="nn-sum"><div><span>Mua</span><b>' + ty(mua) + '</b></div><div><span>Bán</span><b>' + ty(ban) + '</b></div>' +
        '<div><span>Ròng</span><b class="' + cls(rong) + '">' + (rong >= 0 ? '+' : '−') + ty(Math.abs(rong)) + '</b></div></div>' +
        '<div class="nn-cols"><div><p>Mua ròng nhiều nhất</p><ol class="clean top-list">' + (muaR.map(dong).join('') || '<li class="br-note">Không có</li>') + '</ol></div>' +
        '<div><p>Bán ròng nhiều nhất</p><ol class="clean top-list">' + (banR.map(dong).join('') || '<li class="br-note">Không có</li>') + '</ol></div></div>' +
        '<p class="br-note">Đơn vị: tỷ đồng.</p>';
    }

    function bang(nhay){
      var sao = docSao();
      $('#saoCount').textContent = sao.length ? '(' + sao.length + ')' : '';
      var list = (M.tab === 'sao' ? M.rows : trongRo()).filter(function(s){
        if(M.tab === 'sao' && sao.indexOf(s.ma) < 0) return false;
        var f = M.filter;
        return !f || s.ma.indexOf(f) > -1 || s.ten.toUpperCase().indexOf(f) > -1 || s.nganh.toUpperCase().indexOf(f) > -1;
      }).sort(function(a, b){
        var x = M.sortKey === 'nn_rong' ? (a.nn_mua || 0) - (a.nn_ban || 0) : a[M.sortKey];
        var y = M.sortKey === 'nn_rong' ? (b.nn_mua || 0) - (b.nn_ban || 0) : b[M.sortKey];
        return (typeof x === 'string' ? x.localeCompare(y, 'vi') : (x || 0) - (y || 0)) * M.dir;
      });
      M.shown = list;
      if(!list.length){
        body.innerHTML = '<div class="wl-empty">' + (M.tab === 'sao' && !M.filter
          ? 'Chưa ghim mã nào. Bấm ☆ ở đầu mỗi dòng (hoặc trong popup) để thêm mã vào danh sách của bạn.'
          : 'Không tìm thấy "' + esc(M.filter) + '".') + '</div>';
        return;
      }
      body.innerHTML = list.map(function(s){
        var mg = mauGia(s), rong = (s.nn_mua || 0) - (s.nn_ban || 0), daSao = sao.indexOf(s.ma) > -1;
        var nhayCls = '';
        if(nhay && M.cu[s.ma] !== undefined && M.cu[s.ma] !== s.gia) nhayCls = s.gia > M.cu[s.ma] ? ' flash-up' : ' flash-down';
        return '<div class="wl-row wl-click' + nhayCls + '" role="row" tabindex="0" data-ma="' + esc(s.ma) + '" aria-label="Xem chi tiết ' + esc(s.ma) + '">' +
          '<span role="cell"><button type="button" class="star-btn' + (daSao ? ' on' : '') + '" data-sao="' + esc(s.ma) + '" aria-pressed="' + daSao + '" aria-label="' + (daSao ? 'Bỏ ghim ' : 'Ghim ') + esc(s.ma) + '">' + (daSao ? '★' : '☆') + '</button></span>' +
          '<span class="wl-ticker ' + mg + '" role="cell">' + esc(s.ma) + '</span>' +
          '<span class="wl-name" role="cell">' + esc(s.ten) + '<small>' + esc(s.nganh) + '</small></span>' +
          '<span class="wl-num tabular c-tc b-ext" role="cell">' + fmt(s.tham_chieu) + '</span>' +
          '<span class="wl-num tabular c-tran b-ext" role="cell">' + fmt(s.tran) + '</span>' +
          '<span class="wl-num tabular c-san b-ext" role="cell">' + fmt(s.san) + '</span>' +
          '<span class="wl-num tabular wl-price ' + mg + '" role="cell">' + fmt(s.gia) + '</span>' +
          '<span class="wl-num tabular ' + mg + '" role="cell">' + pct(s.thay_doi) + '</span>' +
          '<span class="wl-num tabular wl-vol" role="cell">' + fmt(s.khoi_luong / 1e6, 2) + '</span>' +
          '<span class="wl-num tabular b-ext" role="cell">' + ty(s.gtgd) + '</span>' +
          '<span class="wl-num tabular b-ext ' + cls(rong) + '" role="cell">' + (s.nn_mua === undefined ? '–' : (rong > 0 ? '+' : rong < 0 ? '−' : '') + ty(Math.abs(rong))) + '</span>' +
          '<span class="wl-spark" role="cell">' + sparkSvg(s.spark, 64, 24, s.spark[s.spark.length - 1] >= s.spark[0] ? '#3DD15C' : '#FF6B61') + '</span></div>';
      }).join('');
    }

    function veHet(nhay){
      $('#mktDate').textContent = moc(M.cp.cap_nhat, M.cp.cap_nhat_luc);
      phien(); the(); veChiSo(); doRong(); noiBat(); khoiNgoai(); bang(nhay);
      banDoNhiet(); // vẽ sau cùng để đo đúng kích thước khung (giãn theo cột bên phải)
      M.cu = {};
      M.rows.forEach(function(s){ M.cu[s.ma] = s.gia; });
    }

    function napDuLieu(){
      return Promise.all([loadChiSo(CHI_SO_CHINH), load('co_phieu.json')]).then(function(res){
        M.cs = res[0]; M.cp = res[1]; M.rows = M.cp.co_phieu;
      });
    }

    // ----- sự kiện (gắn một lần, dùng uỷ quyền vì nội dung được vẽ lại)
    $('#mktCards').addEventListener('click', function(e){
      var b = e.target.closest('.index-card'); if(!b) return;
      M.current = b.getAttribute('data-k');
      $$('#mktCards .index-card').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
      veChiSo();
    });
    bindRange($('#mktRange'), M.months, function(m){ M.months = m; veChiSo(); });
    function datRo(ro){
      M.ro = ro;
      try{ localStorage.setItem('kcn-ro', ro); }catch(e){}
      $$('#mktScope button').forEach(function(x){ x.setAttribute('aria-pressed', String(x.getAttribute('data-ro') === ro)); });
      var TEN_RO = {FTSE27: 'FTSE All-Cap', FTSE6: 'FTSE All-World'};
      $$('.ro-ten').forEach(function(x){ x.textContent = TEN_RO[ro] || ro; });
      var gc = $('#mktScopeNote');
      if(gc) gc.hidden = ro.indexOf('FTSE') !== 0;
    }
    datRo(M.ro);
    $$('#mktScope button').forEach(function(b){
      b.addEventListener('click', function(){
        datRo(b.getAttribute('data-ro'));
        doRong(); noiBat(); khoiNgoai(); bang(false); banDoNhiet();
      });
    });
    $$('#mktTopTabs button').forEach(function(b){
      b.addEventListener('click', function(){
        M.top = b.getAttribute('data-t');
        $$('#mktTopTabs button').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
        noiBat();
      });
    });
    $$('#mktTabs button').forEach(function(b){
      b.addEventListener('click', function(){
        M.tab = b.getAttribute('data-tab');
        $$('#mktTabs button').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
        bang(false);
      });
    });
    ['#mktHeat', '#mktTop', '#mktForeign'].forEach(function(id){
      $(id).addEventListener('click', function(e){ var b = e.target.closest('[data-ma]'); if(b) moRow(b.getAttribute('data-ma')); });
      $(id).addEventListener('mouseover', function(e){ var b = e.target.closest('[data-ma]'); if(b) modal.prefetch(b.getAttribute('data-ma')); });
    });
    $$('.wl-head button').forEach(function(btn){
      btn.addEventListener('click', function(){
        var k = btn.getAttribute('data-sort');
        if(k === M.sortKey) M.dir = -M.dir; else { M.sortKey = k; M.dir = (k === 'ma' || k === 'ten') ? 1 : -1; }
        $$('.wl-head button').forEach(function(b){
          $('.arrow', b).textContent = b === btn ? (M.dir > 0 ? '↑' : '↓') : '';
          b.parentNode.setAttribute('aria-sort', b === btn ? (M.dir > 0 ? 'ascending' : 'descending') : 'none');
        });
        bang(false);
      });
    });
    var search = $('#siteSearch');
    var q = new URLSearchParams(location.search).get('q');
    if(q){ M.filter = q.trim().toUpperCase(); if(search) search.value = q; }
    if(search) search.addEventListener('input', function(){ M.filter = search.value.trim().toUpperCase(); bang(false); });
    body.addEventListener('click', function(e){
      var st = e.target.closest('[data-sao]');
      if(st){ e.stopPropagation(); doiSao(st.getAttribute('data-sao')); return; }
      var r = e.target.closest('.wl-click'); if(r) moRow(r.getAttribute('data-ma'));
    });
    body.addEventListener('keydown', function(e){
      if(e.target.closest('[data-sao]')) return;
      var r = e.target.closest('.wl-click');
      if(r && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); moRow(r.getAttribute('data-ma')); }
    });
    ['mouseover', 'focusin', 'touchstart'].forEach(function(ev){
      body.addEventListener(ev, function(e){ var r = e.target.closest('.wl-click'); if(r) modal.prefetch(r.getAttribute('data-ma')); }, {passive: true});
    });
    document.addEventListener('kcn-sao', function(){ bang(false); });
    var hen = null;
    if(window.ResizeObserver){
      var kichCu = '';
      new ResizeObserver(function(){
        var k = $('#mktHeat').clientWidth + 'x' + $('#mktHeat').clientHeight;
        if(k !== kichCu && M.rows.length){ kichCu = k; clearTimeout(hen); hen = setTimeout(banDoNhiet, 80); }
      }).observe($('#mktHeat'));
    }else window.addEventListener('resize', function(){ clearTimeout(hen); hen = setTimeout(banDoNhiet, 150); });
    setInterval(phien, 30000);
    (window.requestIdleCallback || function(f){ setTimeout(f, 1500); })(function(){ loadLwc().catch(function(){}); });

    // mở popup theo mã (từ ô tìm kiếm hoặc link #ma=FPT)
    function moMa(m0){
      m0 = String(m0).toUpperCase();
      return load('danh_muc_ma.json').catch(function(){ return []; }).then(function(dm){
        var r0 = rowCua(m0), e0 = dm.filter(function(x){ return x.ma === m0; })[0];
        if(r0) modal.open(m0, r0);
        else if(e0) modal.open(m0, {ten: e0.ten, nganh: e0.nhom, gia: null, thay_doi: null});
      });
    }
    window.KCN_moPopup = moMa;

    // ----- so sánh cổ phiếu (tối đa 4 mã)
    var cmp = {ds: [], thang: 12, chart: LineChart($('#cmpChart'), {label: 'So sánh hiệu suất cổ phiếu'})};
    try{ var cmpLuu = JSON.parse(localStorage.getItem('kcn-so-sanh')); if(Array.isArray(cmpLuu)) cmp.ds = cmpLuu.slice(0, 4); }catch(e){}
    if(!cmp.ds.length) cmp.ds = ['FPT', 'VCB', 'HPG'];
    var MAU_SS = ['#8DA6EC', '#C6E010', '#F0A35E', '#4CC3B0'];
    function veSoSanh(){
      try{ localStorage.setItem('kcn-so-sanh', JSON.stringify(cmp.ds)); }catch(e){}
      $('#cmpChips').innerHTML = cmp.ds.map(function(m, i){
        return '<button type="button" class="sm-chip-ind" data-bo="' + esc(m) + '" aria-label="Bỏ ' + esc(m) + '"><i style="background:' + MAU_SS[i] + '"></i>' + esc(m) + ' <span aria-hidden="true">×</span></button>';
      }).join('');
      $('#cmpInput').disabled = cmp.ds.length >= 4;
      $('#cmpInput').placeholder = cmp.ds.length >= 4 ? 'Tối đa 4 mã' : '+ Thêm mã (VD: FPT)';
      Promise.all(cmp.ds.map(function(m){ return load('cp/' + m + '.json').catch(function(){ return null; }); })).then(function(ds){
        var series = ds.map(function(x, i){ return x ? {name: x.ma, color: MAU_SS[i], d: x.d, c: x.c} : null; }).filter(Boolean);
        if(series.length) cmp.chart.render(series, cmp.thang, true);
        else $('#cmpChart').querySelector('svg').innerHTML = '';
      });
    }
    bindRange($('#cmpRange'), cmp.thang, function(m){ cmp.thang = m; veSoSanh(); });
    $('#cmpChips').addEventListener('click', function(e){
      var b = e.target.closest('[data-bo]'); if(!b) return;
      cmp.ds = cmp.ds.filter(function(m){ return m !== b.getAttribute('data-bo'); });
      veSoSanh();
    });
    load('danh_muc_ma.json').then(function(dm){
      $('#cmpList').innerHTML = dm.map(function(x){ return '<option value="' + esc(x.ma) + '">' + esc(x.ten) + '</option>'; }).join('');
      function them(){
        var v = $('#cmpInput').value.trim().toUpperCase();
        if(!v) return;
        if(!dm.some(function(x){ return x.ma === v; })){ $('#cmpInput').setCustomValidity('Chưa có dữ liệu mã ' + v); $('#cmpInput').reportValidity(); return; }
        $('#cmpInput').setCustomValidity('');
        if(cmp.ds.indexOf(v) < 0 && cmp.ds.length < 4) cmp.ds.push(v);
        $('#cmpInput').value = '';
        veSoSanh();
      }
      $('#cmpInput').addEventListener('change', them);
      $('#cmpInput').addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); them(); } });
    }).catch(function(){});

    // cập nhật tại chỗ khi có dữ liệu mới (không tải lại trang), giá đổi thì nháy màu
    window.KCN_lamMoi = function(){
      ['co_phieu.json', 'chi_so_ngay.json'].concat(CHI_SO_CHINH.map(function(k){ return 'chi_so/' + k + '.json'; })).forEach(function(f){ delete cache[f]; });
      return napDuLieu().then(function(){ veHet(true); });
    };

    napDuLieu().then(function(){
      veHet(false);
      veSoSanh();
      var h = location.hash.match(/ma=([A-Z0-9]+)/i);
      if(h){
        var cbm = location.hash.match(/cb=([a-z0-9,]*)/i);
        if(cbm) modal.setActive(cbm[1] ? cbm[1].toLowerCase().split(',') : []);
        moMa(h[1]);
      }
      window.addEventListener('hashchange', function(){
        var h2 = location.hash.match(/ma=([A-Z0-9]+)/i);
        if(h2 && $('#smCode').textContent !== h2[1].toUpperCase()) moMa(h2[1]);
      });
    }).catch(function(){ fail(mkt); });
  }

  // =====================================================================
  // TRANG DANH SÁCH ETF
  // =====================================================================
  var etfTable = $('#etfTable');
  if(etfTable){
    Promise.all([load('etf.json'), load('chi_so/danh_sach.json').catch(function(){ return {}; }), loadChiSo(['VN30'])]).then(function(res){
      var data = res[0], cs = res[2], quy = data.quy;
      Object.keys(res[1]).forEach(function(k){ if(!cs[k]) cs[k] = {ten: res[1][k]}; });
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
    load('etf.json').then(function(etfData){
      var q0 = etfData.quy.filter(function(x){ return x.ma === ma; })[0];
      return loadChiSo(q0 && q0.tham_chieu ? [q0.tham_chieu] : []).then(function(cs){ return [etfData, cs]; });
    }).then(function(res){
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
        danhMucQuy(q);
      });
    }).catch(function(){ fail(etfDetail); });
  }

  // danh sách mã trong rổ chỉ số mà quỹ bám theo (ước tính, xem cảnh báo trên trang)
  function danhMucQuy(q){
    var box = $('#dHold');
    if(!box || !q.tham_chieu) return;
    load('ro_chi_so/' + q.tham_chieu + '.json').then(function(ro){
      if(!ro || !ro.thanh_phan || !ro.thanh_phan.length) return;
      box.hidden = false;
      var ten = {VN30: 'VN30', VN100: 'VN100', VNDIAMOND: 'VN Diamond', VNFINLEAD: 'VNFIN Lead', VNFINSELECT: 'VNFIN Select', VNX50: 'VNX50'}[q.tham_chieu] || q.tham_chieu;
      $('#dHoldSub').textContent = q.ma + ' bám theo chỉ số ' + ten + ' gồm ' + ro.so_ma + ' cổ phiếu. Giá cập nhật ' + moc(ro.cap_nhat, ro.cap_nhat_luc) + '.';
      var nh = $('#dHoldNgay');
      if(nh) nh.textContent = ro.ngay_he_so ? ngayVN(ro.ngay_he_so) : 'chưa có';
      if(ro.ty_trong_nguon !== 'free_float'){
        $('#dHoldSub').textContent += ' Rổ này chưa có số free-float nên tỷ trọng chỉ ước tính theo vốn hoá niêm yết.';
      }
      var full = false;
      load('danh_muc_ma.json').catch(function(){ return []; }).then(function(dm){
        var co = {}; dm.forEach(function(x){ co[x.ma] = 1; });
        function ve(){
          var ds = full ? ro.thanh_phan : ro.thanh_phan.slice(0, 15);
          $('#dHoldBody').innerHTML = ds.map(function(x, i){
            var ma = co[x.ma] ? '<a href="' + BASE + '/thi-truong/#ma=' + esc(x.ma) + '"><b>' + esc(x.ma) + '</b></a>' : '<b>' + esc(x.ma) + '</b>';
            return '<tr><td class="num muted">' + (i + 1) + '</td><td>' + ma + '<span class="sub">' + esc(x.nganh) + ' · ' + esc(x.ten) + '</span></td>' +
              '<td class="num">' + fmt(x.gia) + '</td><td class="num ' + cls(x.thay_doi) + '">' + pct(x.thay_doi) + '</td>' +
              '<td class="num"><span class="wbar"><i style="width:' + Math.min(100, x.ty_trong / ro.thanh_phan[0].ty_trong * 100) + '%"></i></span>' + fmt(x.ty_trong, 2) + '%</td></tr>';
          }).join('');
          var nut = $('#dHoldToggle');
          nut.hidden = ro.thanh_phan.length <= 15;
          nut.textContent = full ? 'Thu gọn, chỉ xem 15 mã lớn nhất' : 'Xem toàn bộ ' + ro.thanh_phan.length + ' mã';
        }
        $('#dHoldToggle').onclick = function(){ full = !full; ve(); };
        ve();
      });
      donut($('#dDonut'), $('#dSectors'), ro.nganh.slice(0, 10));
      $('#dHoldCsv').onclick = function(){
        var dong = ['STT,Ma,Ten,Nganh,Gia (dong),Thay doi (%),Von hoa (dong),Ty trong trong ro (%)'];
        ro.thanh_phan.forEach(function(x, i){
          dong.push([i + 1, x.ma, '"' + x.ten.replace(/"/g, '""') + '"', '"' + x.nganh + '"', x.gia, x.thay_doi, x.von_hoa, x.ty_trong].join(','));
        });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob(['\ufeff' + dong.join('\n')], {type: 'text/csv;charset=utf-8'}));
        a.download = q.ma + '_ro_' + q.tham_chieu + '_' + ro.cap_nhat + '.csv';
        document.body.appendChild(a); a.click(); a.remove();
      };
    }).catch(function(){});
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
  // =====================================================================
  // Ô TÌM KIẾM: gợi ý mã, chọn là mở popup chi tiết
  // =====================================================================
  var oTim = $('#siteSearch'), dsGoiY = $('#searchList');
  if(oTim && dsGoiY){
    var danhMuc = null, goiY = [], chon = -1;
    function boDau(x){
      return String(x).normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toUpperCase();
    }
    function napDanhMuc(){
      if(!danhMuc) danhMuc = load('danh_muc_ma.json').then(function(d){
        return d.map(function(x){ x.khoa = boDau(x.ten); return x; });
      }).catch(function(){ danhMuc = null; return []; });
      return danhMuc;
    }
    function dong(){ dsGoiY.hidden = true; oTim.setAttribute('aria-expanded', 'false'); chon = -1; }
    function ve(){
      dsGoiY.innerHTML = goiY.length ? goiY.map(function(x, i){
        return '<li role="option" id="goiy-' + i + '" aria-selected="' + (i === chon) + '" data-ma="' + esc(x.ma) + '">' +
          '<b>' + esc(x.ma) + '</b><span>' + esc(x.ten) + '</span><em>' + (x.loai === 'etf' ? 'ETF' : esc(x.nhom)) + '</em></li>';
      }).join('') : '<li class="search-empty">Chưa có dữ liệu mã này. Hiện hỗ trợ rổ VN30 và các quỹ ETF.</li>';
      dsGoiY.hidden = false;
      oTim.setAttribute('aria-expanded', 'true');
      if(chon > -1) oTim.setAttribute('aria-activedescendant', 'goiy-' + chon); else oTim.removeAttribute('aria-activedescendant');
    }
    function moMa(ma){
      dong();
      oTim.blur();
      var khung = $('#searchWrap'); if(khung) khung.classList.remove('open');
      if(window.KCN_moPopup) window.KCN_moPopup(ma);
      else location.href = oTim.getAttribute('data-market-url') + '#ma=' + encodeURIComponent(ma);
    }
    oTim.addEventListener('focus', napDanhMuc);
    oTim.addEventListener('input', function(){
      var q = boDau(oTim.value.trim());
      if(!q){ dong(); return; }
      napDanhMuc().then(function(d){
        var dau = d.filter(function(x){ return x.ma.indexOf(q) === 0; });
        var khac = d.filter(function(x){ return x.ma.indexOf(q) !== 0 && (x.ma.indexOf(q) > -1 || x.khoa.indexOf(q) > -1); });
        goiY = dau.concat(khac).slice(0, 8);
        chon = goiY.length ? 0 : -1;
        ve();
      });
    });
    oTim.addEventListener('keydown', function(e){
      if(e.key === 'ArrowDown' && !dsGoiY.hidden){ e.preventDefault(); chon = Math.min(goiY.length - 1, chon + 1); ve(); }
      else if(e.key === 'ArrowUp' && !dsGoiY.hidden){ e.preventDefault(); chon = Math.max(0, chon - 1); ve(); }
      else if(e.key === 'Escape'){ dong(); }
      else if(e.key === 'Enter'){
        e.preventDefault();
        var q = boDau(oTim.value.trim());
        if(goiY[chon] && !dsGoiY.hidden) moMa(goiY[chon].ma);
        else if(q) napDanhMuc().then(function(d){ if(d.some(function(x){ return x.ma === q; })) moMa(q); });
      }
    });
    dsGoiY.addEventListener('mousedown', function(e){
      var li = e.target.closest('li[data-ma]');
      if(li){ e.preventDefault(); moMa(li.getAttribute('data-ma')); }
    });
    oTim.addEventListener('blur', function(){ setTimeout(dong, 150); });

    // nút kính lúp trên điện thoại
    var nutTim = $('#searchToggle'), khungTim = $('#searchWrap');
    if(nutTim && khungTim){
      nutTim.addEventListener('click', function(){
        var mo = khungTim.classList.toggle('open');
        nutTim.setAttribute('aria-expanded', String(mo));
        if(mo) setTimeout(function(){ oTim.focus(); }, 50);
      });
    }
  }

  // =====================================================================
  // TRANG QUỸ NẮM GIỮ
  // =====================================================================
  var holdPage = $('#holdPage');
  if(holdPage){
    load('quy_nam_giu.json').then(function(d){
      var ds = d.co_phieu, sortKey = 'so_quy', filter = '', soDong = 30, meta = (d.quy_nn_meta || []).slice();
      function doTre(ngayDanhMuc, ngayThuThap){
        if(!ngayDanhMuc || !ngayThuThap) return null;
        var mocDanhMuc = Date.parse(ngayDanhMuc + 'T00:00:00Z');
        var mocThuThap = Date.parse(ngayThuThap + 'T00:00:00Z');
        return isFinite(mocDanhMuc) && isFinite(mocThuThap)
          ? Math.round((mocThuThap - mocDanhMuc) / 86400000) : null;
      }
      var thienHoang = meta.findIndex(function(q){ return q.ma === 'Tianhong' || q.ma === '008763'; });
      var vwo = meta.findIndex(function(q){ return q.ma === 'VWO'; });
      if(thienHoang > vwo && vwo > -1) meta.splice(vwo, 0, meta.splice(thienHoang, 1)[0]);
      $('#hNN').innerHTML = meta.map(function(q){
        var source = q.nguon
          ? '<a href="' + esc(q.nguon) + '" rel="noopener">Nguồn dữ liệu: ' + esc(q.nguon_ten || 'liên kết nguồn') + '</a>'
          : 'Chưa lấy được dữ liệu nguồn';
        var fetched = q.ngay_thu_thap
          ? ' · Hệ thống thu thập ' + ngayVN(q.ngay_thu_thap) +
            (doTre(q.ngay, q.ngay_thu_thap) === null ? '' : ' · độ trễ tại lúc thu thập ' + doTre(q.ngay, q.ngay_thu_thap) + ' ngày')
          : ' · Chưa lưu ngày hệ thống thu thập snapshot này';
        if(q.ngay_cong_bo){
          fetched += ' · Ngày công bố ' + ngayVN(q.ngay_cong_bo);
        }else{
          fetched += ' · Nguồn không nêu ngày công bố riêng';
        }
        if(q.chu_ky_nguon) fetched += ' · Chu kỳ nguồn ' + esc(q.chu_ky_nguon);
        var age = doTre(q.ngay, q.ngay_thu_thap);
        if(age !== null && Number(q.nguong_tre_ngay) > 0 && age > Number(q.nguong_tre_ngay)){
          fetched += ' · snapshot vượt ngưỡng tuổi dữ liệu theo dõi (' + age + ' ngày)';
        }
        if(q.trang_thai_doi_chieu !== 'da_doi_chieu'){
          fetched += ' · Chưa đối chiếu độc lập với báo cáo gốc';
        }
        if(q.tep_nguon) fetched += ' · <a href="' + esc(q.tep_nguon) + '" rel="noopener">Tệp/bảng danh mục</a>';
        var sourceStatus = q.trang_thai_nguon === 'loi_nguon'
          ? '<p class="nn-meta"><b>Nguồn lỗi ở lần cập nhật gần nhất.</b> Đang giữ dữ liệu snapshot cũ nếu có.</p>'
          : '';
        if(!q.so_ma){
          var emptyMessage = q.trang_thai_nguon === 'loi_nguon'
            ? 'Không tải được danh mục kỳ mới nhất. Danh sách rỗng không có nghĩa quỹ không nắm giữ cổ phiếu Việt Nam.'
            : 'Chưa thấy mã Việt Nam trong danh mục được lọc ở kỳ này. Đây không phải khẳng định quỹ không nắm giữ chứng khoán khác; hãy chờ đối chiếu danh mục ở kỳ công bố tiếp theo.';
          return '<article class="nn-card nn-wait"><header><b>' + esc(q.ma) + '</b><span>' + esc(q.ten) + '</span></header>' +
            '<p class="nn-meta">Ngày danh mục <b>' + ngayVN(q.ngay) + '</b>' + (q.tong_ma_quy ? ' · ' + fmt(q.tong_ma_quy) + ' cổ phiếu toàn cầu' : '') + fetched + ' · ' + source + '</p>' +
            '<p class="nn-meta">' + esc(q.loai_quy || '') + (q.chien_luoc ? ' · ' + esc(q.chien_luoc) : '') + '. ' + esc(q.pham_vi || '') + '</p>' + sourceStatus +
            '<p class="nn-empty"><b>' + esc(emptyMessage) + '</b></p>' +
            '<button type="button" class="btn btn-ghost nn-detail" data-fund="' + esc(q.ma) + '">» Chi tiết</button></article>';
        }
        var th = q.them, extra = '';
        if(th){
          var qm = th.quy_mo_ty_ndt || [], cuoi = qm[qm.length - 1], dau = qm[qm.length - 2];
          extra = '<p class="nn-meta nn-extra">' + esc(th.loai_quy) + '. ' + (cuoi ? 'Quy mô <b>' + fmt(cuoi.gia_tri, 2) + ' tỷ NDT</b> (' + ngayVN(cuoi.ngay) + (dau ? ', quý trước ' + fmt(dau.gia_tri, 2) : '') + ')' : '') +
            (th.co_phieu_pct ? ' · cổ phiếu chiếm ' + fmt(th.co_phieu_pct, 1) + '% tài sản, tiền mặt ' + fmt(th.tien_mat_pct, 1) + '%' : '') + (th.chi_top ? '. Chỉ công bố <b>top ' + th.chi_top + '</b> mã mỗi kỳ báo cáo.' : '.') + '</p>';
        }
        var holdings = q.danh_muc || q.top;
        return '<article class="nn-card"><header><b>' + esc(q.ma) + '</b><span>' + esc(q.ten) + '</span></header>' +
          '<p class="nn-meta">' + esc(q.loai_quy || 'Quỹ nước ngoài') + (q.chien_luoc ? ' · ' + esc(q.chien_luoc) : '') + '<br>Danh mục ngày <b>' + ngayVN(q.ngay) + '</b> · ' + esc(q.pham_vi || (q.so_ma + ' mã Việt Nam')) + fetched + ' · ' + source + '</p>' + sourceStatus + extra +
          '<ol class="clean nn-top">' + q.top.map(function(t){
            return '<li><button type="button" data-ma="' + esc(t.ma) + '"><b>' + esc(t.ma) + '</b><span class="tl-bar"><i class="acc-bg" style="width:' + (t.pct / q.top[0].pct * 100) + '%"></i></span><em>' + fmt(t.pct, 2) + '%</em></button></li>';
          }).join('') + '</ol>' +
          (holdings && holdings.length ? '<button type="button" class="btn btn-ghost nn-detail" data-fund="' + esc(q.ma) + '">» Chi tiết</button>' : '') +
          '</article>';
      }).join('') || '<p class="muted">Chưa lấy được danh mục quỹ nước ngoài.</p>';
      load('chi_so_tham_chieu.json').then(function(c){
        var x = c.xtrackers; if(!x || !x.ten) return;
        var st = c.stoxx, sw = c.ro_swap, tp = x.thanh_phan_chi_so;
        var maxp = tp.top[0].pct;
        $('#hXt').hidden = false;
        $('#hXtBody').innerHTML =
          '<article class="nn-card"><header><b>' + esc(x.ten) + '</b><span>ISIN ' + esc(x.isin) + ' · ra mắt ' + ngayVN(x.ra_mat) + '</span></header>' +
          '<dl class="xt-facts">' +
            '<div><dt>Quy mô quỹ</dt><dd>' + fmt(x.aum_trieu_eur, 2) + ' triệu EUR</dd></div>' +
            '<div><dt>NAV</dt><dd>' + fmt(x.nav_usd, 2) + ' USD · ' + fmt(x.nav_eur, 2) + ' EUR</dd></div>' +
            '<div><dt>Phí (TER)</dt><dd>' + fmt(x.ter_pct, 2) + '%/năm</dd></div>' +
            '<div><dt>Bám chỉ số</dt><dd>STOXX Vietnam Total Market Liquid</dd></div>' +
          '</dl><p class="nn-meta">Số liệu DWS chốt <b>' + ngayVN(x.ngay) + '</b> (cập nhật thủ công) · từ ' + ngayVN(x.chi_so_tu_ngay) + ' đổi chỉ số bám từ <b>' + esc(x.chi_so_truoc) + '</b> sang STOXX · <a href="' + esc(x.nguon_trang) + '" rel="noopener">Nguồn: DWS</a></p>' +
          (sw ? '<p class="xt-swap"><b>Danh mục thật của quỹ (rổ thế chấp swap):</b> ' + sw.so_ma + ' cổ phiếu, ' + fmt(sw.tong_my_pct, 0) + '% là cổ phiếu Mỹ, lớn nhất ' +
            sw.top.slice(0, 3).map(function(t){ return esc(t.ten) + ' ' + fmt(t.pct, 1) + '%'; }).join(', ') + '.</p>' : '') + '</article>' +
          '<article class="nn-card"><header><b>Thành phần chỉ số STOXX Vietnam TML</b><span>Mã trong chỉ số mà quỹ mô phỏng</span></header>' +
          '<p class="nn-meta">Tỷ trọng top 5 theo DWS ngày <b>' + ngayVN(tp.ngay) + '</b>' + (st ? ' · mức chỉ số hiện tại <b>' + fmt(st.gia_tri, 1) + '</b> điểm (STOXX)' : '') + ' · <a href="https://stoxx.com/index/stcvnll/" rel="noopener">Nguồn: STOXX</a></p>' +
          '<ol class="clean nn-top">' + tp.top.map(function(t){
            return '<li><button type="button" data-ma="' + esc(t.ma) + '"><b>' + esc(t.ma) + '</b><span class="tl-bar"><i class="acc-bg" style="width:' + (t.pct / maxp * 100) + '%"></i></span><em>' + fmt(t.pct, 2) + '%</em></button></li>';
          }).join('') + '</ol>' +
          '<p class="nn-meta" style="margin-top:8px;">Các mã còn lại chiếm ' + fmt(tp.khac_pct, 2) + '%.' + (st ? ' Thứ tự top 10 hiện tại theo STOXX: ' + st.top.map(function(t){ return esc(t.ma || t.ten); }).join(' › ') + '.' : '') + '</p>' +
          '<p class="nn-meta xt-warn">Lưu ý: DWS ghi chỉ số giới hạn mã lớn nhất ở 15% nhưng bảng thành phần lại ghi VIC 28,07% (ngày 30/06/2026), nên tỷ trọng top 5 có thể chưa phản ánh đúng sau lần cơ cấu gần nhất. Hãy đối chiếu với STOXX trước khi dùng.</p></article>';
      }).catch(function(){});
      var fundOv = $('#hFundOverlay'), fundDlg = $('.hd-fund', fundOv), fundLastFocus = null;
      function moQuy(ma){
        var q = meta.filter(function(item){ return item.ma === ma; })[0];
        if(!q) return;
        var holdings = q.danh_muc || q.top || [], th = q.them || {};
        fundLastFocus = document.activeElement;
        $('#hFundCode').textContent = q.ma;
        $('#hFundName').textContent = q.ten;
        $('#hFundNote').textContent = holdings.length
          ? 'Danh mục ngày ' + ngayVN(q.ngay) + ' · ' + holdings.length +
            ' mã cổ phiếu Việt Nam trong dữ liệu nguồn.' +
            (th.chi_top ? ' Nguồn chỉ công bố top ' + th.chi_top + ' mã.' : '')
          : q.trang_thai_nguon === 'loi_nguon'
            ? 'Không tải được danh mục mới nhất; danh sách rỗng không xác nhận quỹ không nắm giữ mã Việt Nam.'
            : 'Kỳ danh mục ' + ngayVN(q.ngay) + ' chưa thấy mã Việt Nam trong tập dữ liệu được lọc. Điều này không có nghĩa quỹ không nắm giữ chứng khoán khác.';
        var mx = holdings.length ? (holdings[0].pct || 1) : 1;
        $('#hFundList').innerHTML = holdings.map(function(t, i){
          return '<li><span>' + (i + 1) + '</span><b>' + esc(t.ma) + '</b><span class="tl-bar"><i class="acc-bg" style="width:' +
            (t.pct / mx * 100) + '%"></i></span><em>' + fmt(t.pct, 2) + '%</em></li>';
        }).join('') || '<li class="muted">Chưa có mã Việt Nam trong danh mục kỳ này.</li>';
        fundOv.hidden = false;
        document.body.classList.add('modal-open');
        fundDlg.focus();
      }
      function dongQuy(){
        fundOv.hidden = true;
        document.body.classList.remove('modal-open');
        if(fundLastFocus) fundLastFocus.focus();
      }
      $('#hFundClose').addEventListener('click', dongQuy);
      fundOv.addEventListener('click', function(e){ if(e.target === fundOv) dongQuy(); });
      document.addEventListener('keydown', function(e){ if(!fundOv.hidden && e.key === 'Escape') dongQuy(); });
      $('#hNN').addEventListener('click', function(e){
        var detail = e.target.closest('[data-fund]');
        if(detail){ moQuy(detail.getAttribute('data-fund')); return; }
        var b = e.target.closest('[data-ma]'); if(b) mo(b.getAttribute('data-ma'));
      });
      $('#hQuyMo').textContent = d.so_quy_mo;
      $('#hEtf').textContent = d.so_etf;
      $('#hNgay').textContent = ngayVN(d.ngay_tu) + ' – ' + ngayVN(d.ngay_den);
      var domesticStatus = d.quy_mo_trang_thai === 'loi_nguon'
        ? (d.quy_mo_thong_bao || 'Nguồn Fmarket lỗi; đang giữ snapshot cũ.')
        : '';
      domesticStatus += d.quy_mo_thu_thap_ngay
        ? (domesticStatus ? ' Lần thu thập thành công gần nhất ' : 'Hệ thống thu thập ') + ngayVN(d.quy_mo_thu_thap_ngay) +
          (doTre(d.ngay_tu, d.quy_mo_thu_thap_ngay) === null || doTre(d.ngay_den, d.quy_mo_thu_thap_ngay) === null
            ? '.' : ' · độ trễ trong mẫu tại lần thu thập ' + doTre(d.ngay_tu, d.quy_mo_thu_thap_ngay) +
              '–' + doTre(d.ngay_den, d.quy_mo_thu_thap_ngay) + ' ngày.')
        : (domesticStatus ? ' Ngày thu thập không được lưu.' : 'Ngày hệ thống thu thập chưa được lưu trong snapshot hiện tại.');
      domesticStatus += ' Chưa đối chiếu độc lập với báo cáo gốc; ngày công bố riêng không được Fmarket cung cấp.';
      $('#hQuyMoStatus').textContent = domesticStatus;
      var domesticSample = d.quy_mo_meta || [];
      if(domesticSample.length){
        $('#hQuyMoSample').hidden = false;
        $('#hQuyMoSampleSummary').textContent = 'Danh sách mẫu và ngày danh mục (' + domesticSample.length + ' quỹ)';
        $('#hQuyMoSampleList').innerHTML = domesticSample.map(function(q){
          var collected = q.ngay_thu_thap
            ? ' · thu thập ' + ngayVN(q.ngay_thu_thap)
            : ' · chưa lưu ngày thu thập';
          var state = q.trang_thai_nguon === 'loi_nguon' ? ' · lỗi nguồn; snapshot cũ' : '';
          return '<li><a href="' + esc(q.nguon || 'https://fmarket.vn/') + '" rel="noopener">' + esc(q.ma) + '</a>' +
            (q.loai_quy ? ' [' + esc(q.loai_quy) + ']' : '') + ' · danh mục ' + ngayVN(q.ngay) +
            collected + state +
            (q.nguon_chi_tiet_trang_thai ? ' · URL chi tiết chưa được lưu trong snapshot này' : '') + '</li>';
        }).join('');
      }

      var auditIssues = 0, auditRows = 0;
      ds.forEach(function(x){
        var mo = x.quy_mo || [], etf = x.etf || [], nn = x.quy_nn || [];
        var pct = mo.map(function(q){ return Number(q.pct); }).filter(function(v){ return isFinite(v); });
        var mean = pct.length ? Math.round(pct.reduce(function(sum, v){ return sum + v; }, 0) / pct.length * 100) / 100 : null;
        var max = pct.length ? Math.max.apply(null, pct) : null;
        auditRows++;
        if(x.so_quy !== mo.length || x.so_etf !== etf.length || (x.so_quy_nn || 0) !== nn.length ||
          (mean === null ? x.pct_tb !== null : Math.abs(Number(x.pct_tb) - mean) > 0.011) ||
          (max === null ? x.pct_max !== null : Math.abs(Number(x.pct_max) - max) > 0.011)){
          auditIssues++;
        }
      });
      var auditMeta = d.quy_nn_meta || [];
      auditMeta.forEach(function(q){
        if(q.danh_muc && q.so_ma !== q.danh_muc.length) auditIssues++;
      });
      $('#hFormulaAudit').textContent = auditIssues
        ? 'CÓ ' + auditIssues + ' sai khác nội bộ trong ' + auditRows + ' mã được rà soát; không nên dùng bảng tổng hợp trước khi kiểm tra lại.'
        : 'Kiểm tra phép tính: đạt — đã tính lại số quỹ, tỷ trọng TB/cao nhất và số ETF theo chỉ số tham chiếu cho ' + auditRows +
          ' mã; danh mục chi tiết khớp số mã công bố ở ' + auditMeta.length + ' thẻ quỹ.';

      load('phan_tich.json').then(function(a){
        var nn = a.dong_tien_nn || {}, mo = a.dong_tien_mo || {};
        $('#hInsightFresh').textContent = 'Phân tích cập nhật ' + moc(a.cap_nhat, a.cap_nhat_luc) +
          (a.ftse && a.ftse.ngay_he_so ? ' · hệ số free-float chốt ' + ngayVN(a.ftse.ngay_he_so) : '');

        var nnRows = (nn.ds || []).slice(0, 4);
        var moRows = (mo.ds || []).slice().sort(function(x, y){ return Math.abs(y.diem || 0) - Math.abs(x.diem || 0); }).slice(0, 3);
        var flowHtml = '';
        if(nnRows.length){
          flowHtml += '<p class="hi-label">ETF ngoại · biến động lượng cổ phiếu công bố</p><ol class="clean hi-list">' +
            nnRows.map(function(x){
              var dates = (x.quy || []).map(function(q){ return [q.tu, q.den]; }).filter(function(q){ return q[0] && q[1]; });
              var period = '';
              if(dates.length){
                var from = dates.map(function(q){ return q[0]; }).sort()[0];
                var to = dates.map(function(q){ return q[1]; }).sort().slice(-1)[0];
                period = ngayVN(from) + '–' + ngayVN(to);
              }
              var funds = (x.quy || []).map(function(q){ return esc(q.ma) + ' ' + (q.chenh_cp > 0 ? '+' : q.chenh_cp < 0 ? '−' : '') + fmt(Math.abs(q.chenh_cp)) + (q.moi ? ' mới' : q.thoat ? ' thoát' : ''); }).join(' · ');
              return '<li><div><b>' + esc(x.ma) + '</b><span>' + esc(x.ten) + '</span></div>' +
                '<strong class="' + cls(x.chenh_cp) + '">' + (x.chenh_cp > 0 ? '+' : x.chenh_cp < 0 ? '−' : '') + fmt(Math.abs(x.chenh_cp)) + ' cp</strong>' +
                '<small>' + esc(funds) + (period ? ' · ' + period : '') + '</small></li>';
            }).join('') + '</ol>';
        }else{
          flowHtml += '<div class="pt-empty"><b>Chưa đủ lịch sử để so sánh lượng nắm giữ công bố của ETF ngoại.</b> Cần ít nhất hai kỳ có số lượng nắm giữ; hiện có ' +
            fmt(nn.so_lan_chup || 0) + ' lần chụp đủ dữ liệu' + (nn.tu_ngay ? ' từ ' + ngayVN(nn.tu_ngay) : '') + '. Chênh lệch lượng nắm giữ không tự xác nhận giao dịch trên sàn.</div>';
        }
        if(moRows.length){
          flowHtml += '<p class="hi-label">Quỹ mở trong nước · biến động top 10</p><ol class="clean hi-list">' +
            moRows.map(function(x){
              return '<li><div><b>' + esc(x.ma) + '</b><span>' + esc(x.ten) + '</span></div>' +
                '<strong class="' + cls(x.diem) + '">' + (x.diem > 0 ? '+' : '') + fmt(x.diem) + ' điểm</strong>' +
                '<small>' + fmt(x.moi) + ' mới xuất hiện trong top 10 · ' + fmt(x.tang) + ' tăng tỷ trọng công bố · ' + fmt(x.giam) + ' giảm tỷ trọng công bố · ' + fmt(x.thoat) + ' không còn trong top 10</small></li>';
            }).join('') + '</ol>';
        }else{
          flowHtml += '<div class="pt-empty hi-empty">Quỹ mở: chưa có đủ hai kỳ công bố cho cùng quỹ để so sánh. Dữ liệu top 10 không cho biết thay đổi ở các mã ngoài top 10.</div>';
        }
        $('#hInsightFlows').innerHTML = flowHtml;
        if(nnRows.length){
          $('#hInsightFlows').insertAdjacentHTML('beforeend', '<p class="hi-footnote">Chênh lệch lượng được công bố giữa các kỳ; chia/tách cổ phiếu, hoán đổi hoặc thay đổi đơn vị quỹ có thể ảnh hưởng số lượng. Giá trị quy đổi không xác nhận lệnh khớp hoặc dòng vốn.</p>');
        }

        var gapMeta = a.lech_pha_meta || {}, gaps = (a.lech_pha || []).slice().sort(function(x, y){ return Math.abs(y.nn_tru_noi || 0) - Math.abs(x.nn_tru_noi || 0); }).slice(0, 4);
        var dateRange = function(rows){
          var dates = rows.map(function(q){ return q.ngay; }).filter(Boolean).sort();
          return dates.length ? ngayVN(dates[0]) + '–' + ngayVN(dates[dates.length - 1]) : 'chưa rõ';
        };
        $('#hInsightGaps').innerHTML = gaps.length
          ? '<ol class="clean hi-list">' + gaps.map(function(x){
              var gap = x.nn_tru_noi;
              return '<li><div><b>' + esc(x.ma) + '</b><span>' + esc(x.ten) + '</span></div>' +
                '<strong class="' + cls(gap) + '">' + (gap > 0 ? '+' : '') + fmt(gap, 2) + ' điểm %</strong>' +
                '<small>VN100 ' + (x.vn100 === null ? 'chưa có' : fmt(x.vn100, 2) + '%') + ' · Nội ' + fmt(x.noi_tb, 2) + '% (' + fmt(x.so_noi) + ' quỹ công bố mã này) · Ngoại ' + fmt(x.ngoai_tb, 2) + '% (' + fmt(x.so_ngoai) + ' quỹ công bố mã này)</small></li>';
            }).join('') + '</ol><p class="hi-footnote">So sánh top 10, mỗi trung bình chỉ tính các quỹ công bố mã đó; vắng mặt không phải 0%. Mẫu nội ' + fmt(gapMeta.noi_so_quy || 0) + ' quỹ, ngày ' + dateRange(gapMeta.noi_mau || []) + '; nước ngoài ' + fmt(gapMeta.ngoai_so_quy || 0) + ' quỹ, ngày ' + dateRange(gapMeta.ngoai_mau || []) + '; loại khỏi mẫu so sánh ' + (gapMeta.ngoai_chua_co_mau || []).length + ' quỹ. Danh sách mẫu và lý do nằm ở bảng Radar. VN100 chốt ' + ngayVN(gapMeta.ngay_vn100) + '. Chênh lệch không chứng minh giao dịch hay nguyên nhân.</p>'
          : '<div class="pt-empty">Chưa có mã được công bố trong top 10 ở cả hai nhóm để so sánh. Thiếu công bố không được xem là tỷ trọng 0.</div>';

        var ft = a.ftse || {}, rowsFt = ft.ds || [];
        var von = $('#hScenarioFund'), tranche = $('#hScenarioTranche'), fx = $('#hScenarioFx'), participation = $('#hScenarioParticipation');
        von.value = ft.von_ty_usd === undefined ? '' : ft.von_ty_usd;
        tranche.value = ft.dot_dau_pct === undefined ? '' : ft.dot_dau_pct;
        fx.value = ft.fx === undefined ? '' : ft.fx;
        var tongFF = rowsFt.reduce(function(sum, x){ return sum + (x.ff_gt || 0); }, 0);
        function veScenario(){
          var vonUsd = Math.max(0, Number(von.value) || 0);
          var dot = Math.min(100, Math.max(0, Number(tranche.value) || 0));
          var tyGia = Math.max(1, Number(fx.value) || Number(ft.fx) || 1);
          var tg = Math.min(100, Math.max(1, Number(participation.value) || 20));
          var tongCau = vonUsd * 1e9 * tyGia * dot / 100;
          var result = rowsFt.map(function(x){
            var w = tongFF ? (x.ff_gt || 0) / tongFF : 0;
            var cau = tongCau * w;
            return {x:x, w:w, cau:cau, sessions:x.adv ? cau / (x.adv * tg / 100) : null};
          }).sort(function(x, y){ return (y.sessions || 0) - (x.sessions || 0); });
          var worst = result.filter(function(x){ return x.sessions !== null; })[0];
          $('#hScenarioTiles').innerHTML =
            '<div class="pt-tile"><small>Tổng cầu theo giả định</small><b>' + fmt(tongCau / 1e12, 1) + ' nghìn tỷ đồng</b></div>' +
            '<div class="pt-tile"><small>Áp lực thanh khoản cao nhất</small><b>' + (worst ? esc(worst.x.ma) + ' · ' + fmt(worst.sessions, 1) + ' phiên' : 'Chưa đủ dữ liệu') + '</b></div>' +
            '<div class="pt-tile"><small>Phạm vi dữ liệu</small><b>' + fmt(rowsFt.length) + ' mã FTSE · ' + (ft.ngay_he_so ? ngayVN(ft.ngay_he_so) : 'chưa rõ ngày hệ số') + '</b></div>';
          $('#hScenarioBody').innerHTML = result.length ? result.slice(0, 5).map(function(r){
            return '<tr><td><b>' + esc(r.x.ma) + '</b><span class="sub">' + esc(r.x.ten) + '</span></td>' +
              '<td class="num">' + fmt(r.w * 100, 2) + '%</td>' +
              '<td class="num">' + fmt(r.cau / 1e9, 0) + '</td>' +
              '<td class="num">' + (r.x.adv ? fmt(r.x.adv / 1e9, 0) : '–') + '</td>' +
              '<td class="num">' + (r.sessions === null ? '–' : fmt(r.sessions, 1)) + '</td></tr>';
          }).join('') : '<tr><td colspan="5" class="empty-row">Chưa có dữ liệu thành phần và free-float.</td></tr>';
          $('#hScenarioMethod').innerHTML =
            'Cách tính: tỷ trọng mã = vốn hoá free-float mã / tổng vốn hoá free-float 27 mã; cầu mã = vốn giả định × tỷ lệ đợt × tỷ trọng; phiên tương đương = cầu mã / (thanh khoản bình quân 20 phiên × tỷ lệ tham gia ' + fmt(tg, 0) + '%). ' +
            'Danh sách đầu vào là 27 mã thuộc rổ FTSE27 theo dữ liệu hiện có. Hệ số free-float chốt ' + (ft.ngay_he_so ? ngayVN(ft.ngay_he_so) : 'chưa rõ ngày') + '. Vốn ' + fmt(vonUsd, 1) + ' tỷ USD và tỷ lệ đợt ' + fmt(dot, 0) + '% là giả định để thử kịch bản, không phải cam kết giải ngân hay tỷ trọng chính thức. ' +
            'Mô hình không tính giới hạn sở hữu nước ngoài, điều chỉnh chỉ số, giao dịch trước ngày hiệu lực hoặc tác động giá; thời gian thực tế có thể khác đáng kể.';
        }
        [von, tranche, fx, participation].forEach(function(input){ input.addEventListener('input', veScenario); });
        if(!rowsFt.length || !tongFF){
          $('#hScenarioBody').innerHTML = '<tr><td colspan="5" class="empty-row">Thiếu dữ liệu free-float để tính kịch bản.</td></tr>';
          $('#hScenarioMethod').textContent = 'Chưa thể tính do thiếu dữ liệu thành phần hoặc free-float.';
        }else veScenario();
      }).catch(function(){
        $('#hInsightFresh').textContent = 'Chưa tải được dữ liệu phân tích.';
        $('#hInsightFlows').innerHTML = '<div class="pt-empty">Không tải được lịch sử biến động danh mục; thử tải lại sau.</div>';
        $('#hInsightGaps').innerHTML = '<div class="pt-empty">Không tải được dữ liệu so sánh; thử tải lại sau.</div>';
        $('#hScenarioMethod').textContent = 'Không tải được dữ liệu đầu vào cho kịch bản.';
      });

      function xep(){
        return ds.filter(function(x){
          var f = filter;
          if((sortKey === 'pct_tb' || sortKey === 'pct_max') && x.so_quy < 5) return false; // require enough top-10 disclosures for an average
          return !f || x.ma.indexOf(f) > -1 || x.nganh.toUpperCase().indexOf(f) > -1 || x.ten.toUpperCase().indexOf(f) > -1;
        }).sort(function(a, b){
          var u = (b[sortKey] || 0) - (a[sortKey] || 0);
          return u || (b.so_quy - a.so_quy) || ((b.pct_tb || 0) - (a.pct_tb || 0));
        });
      }
      function ve(){
        var list = xep();
        $('#hBody').innerHTML = list.slice(0, soDong).map(function(x, i){
          var tl = d.so_quy_mo ? x.so_quy / d.so_quy_mo * 100 : 0;
          return '<tr class="hold-row" tabindex="0" data-ma="' + esc(x.ma) + '"><td class="num muted">' + (i + 1) + '</td>' +
            '<td><b>' + esc(x.ma) + '</b><span class="sub">' + esc(x.nganh) + ' · ' + esc(x.ten) + '</span></td>' +
            '<td class="num"><b>' + x.so_quy + '</b><small class="muted">/' + d.so_quy_mo + ' top 10</small></td>' +
            '<td class="num hide-sm"><span class="wbar"><i style="width:' + tl + '%"></i></span>' + fmt(tl, 0) + '%</td>' +
            '<td class="num">' + (x.pct_tb === null ? '–' : fmt(x.pct_tb, 2) + '%') + '</td>' +
            '<td class="num hide-sm">' + (x.pct_max === null ? '–' : fmt(x.pct_max, 1) + '%') + '</td>' +
            '<td class="num">' + x.so_etf + '<small class="muted">/' + d.so_etf + ' ETF chỉ số</small></td>' +
            '<td class="num hide-sm">' + (x.so_quy_nn ? x.quy_nn.map(function(q){ return esc(q.ma) + ' ' + fmt(q.pct, 1) + '%'; }).join(' · ') : '<span class="muted">–</span>') + '</td></tr>';
        }).join('') || '<tr><td colspan="8" class="empty-row">Không tìm thấy mã phù hợp.</td></tr>';
        var nut = $('#hMore');
        nut.hidden = list.length <= soDong;
        nut.textContent = 'Xem thêm (' + (list.length - soDong) + ' mã nữa)';
        var gc = $('#hNote');
        if(gc) gc.hidden = !(sortKey === 'pct_tb' || sortKey === 'pct_max');
      }

      // 6 mã xuất hiện trong top 10 của nhiều quỹ mở nhất
      var top6 = ds.slice().sort(function(a, b){ return (b.so_quy - a.so_quy) || ((b.pct_tb || 0) - (a.pct_tb || 0)); }).slice(0, 6);
      $('#hTop6').innerHTML = top6.map(function(x, i){
        return '<button type="button" class="top6-card" data-ma="' + esc(x.ma) + '"><span class="top6-rank">#' + (i + 1) + '</span><b>' + esc(x.ma) + '</b>' +
          '<span class="top6-n">' + x.so_quy + '<small>/' + d.so_quy_mo + ' quỹ xuất hiện top 10</small></span>' +
          '<span class="top6-s">% NAV trung bình <b>' + fmt(x.pct_tb, 1) + '%</b> · cao nhất ' + fmt(x.pct_max, 1) + '%</span>' +
          '<span class="top6-s">' + x.so_etf + '/' + d.so_etf + ' ETF có mã trong chỉ số tham chiếu</span></button>';
      }).join('');

      // cửa sổ chi tiết: quỹ nào đang giữ một mã
      var ov = $('#hOverlay'), dlg = $('.hd', ov), cuoi = null;
      function mo(ma){
        var x = ds.filter(function(y){ return y.ma === ma; })[0];
        if(!x) return;
        cuoi = document.activeElement;
        $('#hdCode').textContent = x.ma;
        $('#hdName').textContent = x.nganh + ' · ' + x.ten;
        $('#hdLink').href = BASE + '/thi-truong/#ma=' + x.ma;
        $('#hdQuyN').textContent = '(' + x.so_quy + ' quỹ mở có mã trong top 10)';
        var mx = x.quy_mo.length ? x.quy_mo[0].pct : 1;
        $('#hdQuy').innerHTML = x.quy_mo.map(function(q){
          return '<li><span class="hd-ma">' + esc(q.ma) + '</span><span class="hd-ten">' + esc(q.ten) + '</span>' +
            '<span class="tl-bar"><i class="acc-bg" style="width:' + (q.pct / mx * 100) + '%"></i></span><b>' + fmt(q.pct, 2) + '%</b></li>';
        }).join('') || '<li class="muted">Không có quỹ mở nào giữ mã này trong top 10.</li>';
        $('#hdEtfN').textContent = '(' + x.so_etf + ' quỹ có mã trong chỉ số tham chiếu)';
        $('#hdEtf').innerHTML = x.etf.map(function(m){
          return '<a class="chip" href="' + BASE + '/etf/chi-tiet/?ma=' + esc(m) + '">' + esc(m) + '</a>';
        }).join('') || '<span class="muted">Không có mã này trong các chỉ số tham chiếu ETF đang theo dõi.</span>';
        $('#hdNNN').textContent = '(' + (x.so_quy_nn || 0) + ' quỹ nước ngoài có công bố mã này)';
        var mn = x.quy_nn && x.quy_nn.length ? x.quy_nn[0].pct : 1;
        $('#hdNN').innerHTML = (x.quy_nn || []).map(function(q){
          return '<li><span class="hd-ma">' + esc(q.ma) + '</span><span class="hd-ten">' + esc(q.ten) + '</span>' +
            '<span class="tl-bar"><i class="acc-bg" style="width:' + (q.pct / mn * 100) + '%"></i></span><b>' + fmt(q.pct, 2) + '%</b></li>';
        }).join('') || '<li class="muted">Không có trong danh mục các quỹ nước ngoài đang theo dõi.</li>';
        ov.hidden = false;
        document.body.classList.add('modal-open');
        dlg.focus();
      }
      function dong(){ ov.hidden = true; document.body.classList.remove('modal-open'); if(cuoi) cuoi.focus(); }
      $('#hdClose').addEventListener('click', dong);
      ov.addEventListener('click', function(e){ if(e.target === ov) dong(); });
      document.addEventListener('keydown', function(e){ if(!ov.hidden && e.key === 'Escape') dong(); });
      $('#hTop6').addEventListener('click', function(e){ var b = e.target.closest('[data-ma]'); if(b) mo(b.getAttribute('data-ma')); });
      $('#hBody').addEventListener('click', function(e){ var r = e.target.closest('[data-ma]'); if(r) mo(r.getAttribute('data-ma')); });
      $('#hBody').addEventListener('keydown', function(e){
        var r = e.target.closest('[data-ma]');
        if(r && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); mo(r.getAttribute('data-ma')); }
      });
      $$('#hSort button').forEach(function(b){
        b.addEventListener('click', function(){
          sortKey = b.getAttribute('data-k');
          $$('#hSort button').forEach(function(x){ x.setAttribute('aria-pressed', String(x === b)); });
          ve();
        });
      });
      $('#hFilter').addEventListener('input', function(e){ filter = e.target.value.trim().toUpperCase(); ve(); });
      $('#hMore').addEventListener('click', function(){ soDong += 30; ve(); });
      ve();
      var h = location.hash.match(/ma=([A-Z0-9]+)/i);
      if(h) mo(h[1].toUpperCase());
    }).catch(function(){ fail(holdPage); });
  }

  // =====================================================================
  // TRANG RADAR DÒNG TIỀN (phan-tich.html)
  // =====================================================================
  var ptPage = $('#ptPage');
  if(ptPage){
    load('phan_tich.json').then(function(d){
      $('#ptNgay').textContent = moc(d.cap_nhat, d.cap_nhat_luc);
      var nutMa = function(m, ten){ return '<b>' + esc(m) + '</b>' + (ten ? '<span class="sub">' + esc(ten) + '</span>' : ''); };
      var dau = function(n){ return n > 0 ? '+' : n < 0 ? '−' : ''; };

      // ---- 1. Radar FTSE (tính ngay trên trình duyệt)
      var ft = d.ftse, oVon = $('#ptVon'), oDot = $('#ptDot'), oFx = $('#ptFx'), oTg = $('#ptTg');
      oVon.value = ft.von_ty_usd; oDot.value = ft.dot_dau_pct; oFx.value = ft.fx; oTg.value = 20;
      var tongFF = ft.ds.reduce(function(s, x){ return s + x.ff_gt; }, 0);
      function veFtse(){
        var von = Math.max(0, parseFloat(oVon.value) || 0), dot = Math.min(100, Math.max(0, parseFloat(oDot.value) || 0)),
            fx = parseFloat(oFx.value) || ft.fx, tg = Math.min(100, Math.max(1, parseFloat(oTg.value) || 20));
        var tong = von * 1e9 * fx * dot / 100;
        var rows = ft.ds.map(function(x){
          var w = x.ff_gt / tongFF, cau = tong * w;
          return {x: x, w: w, cau: cau, pff: cau / x.ff_gt * 100, ngay: x.adv ? cau / (x.adv * tg / 100) : null};
        });
        rows.sort(function(a, b){ return (b.ngay || 0) - (a.ngay || 0); });
        var nong = rows.filter(function(r){ return r.ngay !== null && r.ngay > 5; }).length;
        var top = rows[0];
        $('#ptTiles').innerHTML =
          '<div class="pt-tile"><small>Tổng cầu mua đợt đầu</small><b>' + fmt(tong / 1e12, 1) + ' nghìn tỷ đồng</b></div>' +
          '<div class="pt-tile"><small>Mã khó hấp thụ nhất</small><b>' + (top ? esc(top.x.ma) + ' · ' + fmt(top.ngay, 1) + ' phiên' : '–') + '</b></div>' +
          '<div class="pt-tile"><small>Số mã cần hơn 5 phiên</small><b>' + nong + '/' + rows.length + '</b></div>';
        $('#ptFtBody').innerHTML = rows.map(function(r){
          return '<tr class="hold-row' + (r.ngay > 5 ? ' pt-nong' : '') + '" tabindex="0" data-ma="' + esc(r.x.ma) + '"><td><b>' + esc(r.x.ma) + '</b>' + (r.x.nhom6 ? '<span class="pt-tag">FTSE All-World</span>' : '') + '<span class="sub">' + esc(r.x.nganh) + ' · ' + esc(r.x.ten) + '</span></td>' +
            '<td class="num">' + fmt(r.w * 100, 1) + '%</td>' +
            '<td class="num">' + fmt(r.cau / 1e9, 0) + '</td>' +
            '<td class="num hide-sm">' + fmt(r.pff, 2) + '%</td>' +
            '<td class="num hide-sm">' + (r.x.adv ? fmt(r.x.adv / 1e9, 0) : '–') + '</td>' +
            '<td class="num">' + (r.ngay === null ? '–' : fmt(r.ngay, 1)) + '</td></tr>';
        }).join('');
        $('#ptFtNote').innerHTML = 'Giả định: tỷ trọng = vốn hoá free-float của tập mã đầu vào' + (ft.ngay_he_so ? ' (chốt ' + ngayVN(ft.ngay_he_so) + ')' : '') + '. Mặc định vốn 2,5 tỷ USD và đợt đầu 25% là tham số mô phỏng, không phải kế hoạch giải ngân hay tỷ trọng chính thức. "Số phiên tương đương" là tỷ lệ giữa cầu mô hình và phần thanh khoản giả định có thể tham gia, không phải thời gian quỹ chắc chắn mua xong.';
      }
      [oVon, oDot, oFx, oTg].forEach(function(o){ o.addEventListener('input', veFtse); });
      veFtse();

      // ---- 2. Biến động lượng công bố của quỹ ETF ngoại
      var nn = d.dong_tien_nn;
      if(!nn.ds.length){
        $('#ptNnBody').innerHTML = '<div class="pt-empty"><b>Đang tích luỹ lịch sử.</b> Kim Chỉ Nam lưu danh mục mỗi khi nguồn công bố bản mới' + (nn.tu_ngay ? ' (đã lưu từ ' + ngayVN(nn.tu_ngay) + ')' : '') + '. Chỉ hiển thị biến động lượng nắm giữ công bố khi có ít nhất hai kỳ so sánh được. VWO/VT chỉ hiện nếu mã Việt Nam được đối chiếu trong danh mục kỳ tiếp theo.</div>';
      } else {
        $('#ptNnBody').innerHTML = '<div class="table-card"><div class="table-scroll"><table class="data-table hold-table"><thead><tr><th scope="col">Cổ phiếu</th><th scope="col" class="num">Δ lượng công bố <small class="muted">(cổ phiếu)</small></th><th scope="col" class="num">Quy đổi theo giá hiện tại <small class="muted">(tỷ đồng)</small></th><th scope="col" class="hide-sm">Quỹ, kỳ so sánh</th></tr></thead><tbody>' +
          nn.ds.map(function(x){
            return '<tr class="hold-row" tabindex="0" data-ma="' + esc(x.ma) + '"><td>' + nutMa(x.ma, x.ten) + '</td>' +
              '<td class="num ' + cls(x.chenh_cp) + '">' + dau(x.chenh_cp) + fmt(Math.abs(x.chenh_cp)) + '</td>' +
              '<td class="num ' + cls(x.chenh_gt) + '">' + dau(x.chenh_gt) + fmt(Math.abs(x.chenh_gt) / 1e9, 2) + '</td>' +
              '<td class="hide-sm pt-quy">' + x.quy.map(function(q){
                return esc(q.ma) + ' ' + dau(q.chenh_cp) + fmt(Math.abs(q.chenh_cp)) + (q.moi ? '<span class="pt-tag">mới xuất hiện</span>' : q.thoat ? '<span class="pt-tag">không còn trong snapshot</span>' : '') + ' <small>(' + ngayVN(q.tu).slice(0, 5) + '→' + ngayVN(q.den).slice(0, 5) + ')</small>';
              }).join(' · ') + '</td></tr>';
          }).join('') + '</tbody></table></div></div><p class="table-note">Δ tính riêng từng quỹ–mã giữa hai lần chụp; giá trị quy đổi theo giá hiện tại, không phải giá giao dịch lịch sử. Chia/tách, hoán đổi, ngày chốt khác nhau và phạm vi nguồn có thể ảnh hưởng kết quả. Đã lưu ' + nn.so_lan_chup + ' lần công bố' + (nn.tu_ngay ? ' từ ' + ngayVN(nn.tu_ngay) : '') + '.</p>';
      }

      // ---- 3. Quỹ mở nội
      var mo = d.dong_tien_mo;
      if(!mo.ds.length){
        $('#ptMoBody').innerHTML = '<div class="pt-empty"><b>Đang tích luỹ lịch sử.</b> Quỹ mở chỉ đổi danh mục theo kỳ (thường hằng tháng). Khi một quỹ công bố danh mục mới, Kim Chỉ Nam so với kỳ trước và hiện mã tăng/giảm tại đây.</div>';
      } else {
        $('#ptMoBody').innerHTML = '<div class="table-card"><div class="table-scroll"><table class="data-table hold-table"><thead><tr><th scope="col">Cổ phiếu</th><th scope="col" class="num">Điểm biến động</th><th scope="col" class="num">Mới vào top 10 / Tăng tỷ trọng</th><th scope="col" class="num">Rời top 10 / Giảm tỷ trọng</th></tr></thead><tbody>' +
          mo.ds.map(function(x){
            return '<tr class="hold-row" tabindex="0" data-ma="' + esc(x.ma) + '"><td>' + nutMa(x.ma, x.ten) + '</td><td class="num ' + cls(x.diem) + '"><b>' + dau(x.diem) + Math.abs(x.diem) + '</b></td>' +
              '<td class="num">' + x.moi + ' / ' + x.tang + '</td><td class="num">' + x.thoat + ' / ' + x.giam + '</td></tr>';
          }).join('') + '</tbody></table></div></div><p class="table-note">Điểm là bộ đếm các thay đổi top 10/tỷ trọng công bố trong mẫu ' + mo.so_quy + ' quỹ có ít nhất hai kỳ; không phải số tiền hay số cổ phiếu mua/bán.</p>';
      }

      // ---- 4. Lệch pha nội - ngoại
      var lpKey = 'ngoai', lpMeta = d.lech_pha_meta || {};
      function veLp(){
        var ds = d.lech_pha.slice().sort(function(a, b){ return lpKey === 'ngoai' ? b.nn_tru_noi - a.nn_tru_noi : a.nn_tru_noi - b.nn_tru_noi; }).slice(0, 15);
        $('#ptLpBody').innerHTML = ds.map(function(x){
          return '<tr class="hold-row" tabindex="0" data-ma="' + esc(x.ma) + '"><td>' + nutMa(x.ma, x.ten) + '</td>' +
            '<td class="num">' + (x.vn100 === null ? '–' : fmt(x.vn100, 2) + '%') + '</td><td class="num">' + fmt(x.noi_tb, 2) + '%</td><td class="num">' + fmt(x.ngoai_tb, 2) + '%</td>' +
            '<td class="num hide-sm">' + x.so_noi + '</td><td class="num hide-sm">' + x.so_ngoai + '</td></tr>';
        }).join('') || '<tr><td colspan="6" class="empty-row">Chưa có mã xuất hiện trong top 10 của cả hai nhóm.</td></tr>';
        var describeSample = function(q){
          return q.ma + ' ' + ngayVN(q.ngay) +
            (q.trang_thai_nguon === 'loi_nguon' ? ' (snapshot cũ; lỗi nguồn)' :
              q.ngay_thu_thap ? ' (thu thập ' + ngayVN(q.ngay_thu_thap) + ')' : ' (chưa lưu ngày thu thập)');
        };
        $('#ptLpMetaSummary').textContent = 'Danh sách mẫu và ngày danh mục (' + (lpMeta.noi_so_quy || 0) + ' quỹ nội, ' + (lpMeta.ngoai_so_quy || 0) + ' quỹ nước ngoài)';
        $('#ptLpMetaContent').textContent = 'Phạm vi top 10 · Quỹ nội (' + (lpMeta.noi_so_quy || 0) + '): ' +
          (lpMeta.noi_mau || []).map(function(q){
            return describeSample(q) + (q.loai_quy ? ' [' + q.loai_quy + ']' : '');
          }).join(', ') +
          ' · Quỹ nước ngoài (' + (lpMeta.ngoai_so_quy || 0) + '): ' +
          (lpMeta.ngoai_mau || []).map(function(q){
            return describeSample(q) + (q.loai_quy ? ' [' + q.loai_quy + ']' : '');
          }).join(', ') +
          ' · Không đưa vào mẫu so sánh: ' + (lpMeta.ngoai_chua_co_mau || []).map(function(q){
            return describeSample(q) + ': ' + (q.ly_do || 'không đủ dữ liệu');
          }).join(', ') +
          ' · VN100 ' + ngayVN(lpMeta.ngay_vn100) +
          '. Ngày công bố riêng chưa được nguồn cung cấp; dữ liệu chưa được đối chiếu độc lập. Trung bình có điều kiện trên các quỹ công bố mã; vắng mặt không đồng nghĩa 0%.';
      }
      $('#ptLpSort').addEventListener('click', function(e){
        var b = e.target.closest('button'); if(!b) return;
        lpKey = b.getAttribute('data-k');
        $$('#ptLpSort button').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        veLp();
      });
      veLp();

      var moMa = function(e){
        var el = e.target.closest('tr[data-ma]'); if(!el) return;
        if(e.type === 'keydown' && e.key !== 'Enter') return;
        var ma = el.getAttribute('data-ma'), o = $('[data-market-url]');
        if(window.KCN_moPopup) window.KCN_moPopup(ma);
        else if(o) location.href = o.getAttribute('data-market-url') + '#ma=' + encodeURIComponent(ma);
      };
      ptPage.addEventListener('click', moMa);
      ptPage.addEventListener('keydown', moMa);
    }).catch(function(){ fail(ptPage); });
  }

  // ---- Cảnh báo và tổng hợp tuần trên trang Radar, và trang Dữ liệu & API
  if(ptPage){
    load('canh_bao.json').then(function(c){
      var ds = (c.ds || []).slice(0, 10);
      $('#ptCbBody').innerHTML = ds.length ? ds.map(function(x){
        var k = x.loai === 'ban_manh' ? ' pt-cb-ban' : x.loai === 'vn_lan_dau' ? ' pt-cb-vn' : '';
        return '<div class="pt-cb' + k + '"><b>' + esc(x.tieu_de) + '</b>' + esc(x.noi_dung) + ' <small>· ' + ngayVN(x.ngay) + '</small></div>';
      }).join('') : '<div class="pt-empty"><b>Chưa có cảnh báo nào.</b> Hệ thống theo dõi biến động lượng nắm giữ công bố đã quy đổi theo giá hiện tại; ngưỡng cảnh báo không xác nhận giao dịch hoặc dòng vốn. VWO/VT chỉ được ghi nhận khi có dữ liệu danh mục Việt Nam để đối chiếu.</div>';
    }).catch(function(){ $('#ptCbBody').innerHTML = '<div class="pt-empty">Chưa tải được cảnh báo.</div>'; });

    load('tong_hop_tuan.json').then(function(t){
      if(!t || !t.mua) return;
      $('#ptTuan').hidden = false;
      $('#ptTuanSub').innerHTML = 'Các kỳ so sánh trong khoảng <b>' + ngayVN(t.tu) + '</b> đến <b>' + ngayVN(t.den) + '</b>; từng quỹ có ngày chốt riêng. Giá trị chỉ là lượng nắm giữ công bố thay đổi quy theo giá hiện tại, không phải dòng tiền hoặc giao dịch.';
      $('#ptTuanTiles').innerHTML =
        '<div class="pt-tile"><small>Δ dương quy đổi</small><b class="up">' + fmt(t.tong_mua / 1e9, 1) + ' tỷ đồng</b></div>' +
        '<div class="pt-tile"><small>Δ âm quy đổi</small><b class="down">' + fmt(Math.abs(t.tong_ban) / 1e9, 1) + ' tỷ đồng</b></div>' +
        '<div class="pt-tile"><small>Quỹ mở nội vừa cập nhật</small><b>' + t.so_quy_mo_moi + ' quỹ</b></div>';
      var bang = function(ds, ten){
        return '<article class="nn-card"><header><b>' + ten + '</b></header><ol class="clean nn-top">' + (ds.length ? ds.map(function(x){
          return '<li><button type="button" data-ma="' + esc(x.ma) + '"><b>' + esc(x.ma) + '</b><span class="sub">' + esc(x.quy.join(', ')) + '</span><em class="' + cls(x.gt) + '">' + (x.gt > 0 ? '+' : '−') + fmt(Math.abs(x.gt) / 1e9, 1) + ' tỷ</em></button></li>';
        }).join('') : '<li class="muted">Không có.</li>') + '</ol></article>';
      };
      $('#ptTuanBody').innerHTML = bang(t.mua, 'Lượng công bố tăng quy đổi lớn nhất') + bang(t.ban, 'Lượng công bố giảm quy đổi lớn nhất');
      $('#ptTuanBody').addEventListener('click', function(e){
        var b = e.target.closest('button[data-ma]'); if(!b) return;
        var ma = b.getAttribute('data-ma'), o = $('[data-market-url]');
        if(window.KCN_moPopup) window.KCN_moPopup(ma);
        else if(o) location.href = o.getAttribute('data-market-url') + '#ma=' + encodeURIComponent(ma);
      });
      $('#ptCopy').addEventListener('click', function(){
        var xong = function(ok){ $('#ptCopyMsg').textContent = ok ? 'Đã sao chép.' : 'Không sao chép được, hãy bôi đen và sao chép thủ công.'; };
        if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(t.van_ban).then(function(){ xong(true); }, function(){ xong(false); }); }
        else xong(false);
      });
    }).catch(function(){});
  }

  var dlPage = $('#dlPage');
  if(dlPage){
    load('muc_luc_du_lieu.json').then(function(m){
      $('#dlTu').textContent = m.ngay_bat_dau ? ngayVN(m.ngay_bat_dau) : '–';
      $('#dlBody').innerHTML = m.datasets.map(function(x){
        var url = BASE + '/assets/data/' + x.tep;
        return '<tr><td><b>' + esc(x.tep.replace('xuat/', '')) + '</b><span class="sub">' + esc(x.mo_ta) + '</span></td>' +
          '<td class="num">' + (x.so_dong !== undefined ? fmt(x.so_dong) : '–') + '</td>' +
          '<td class="hide-sm pt-quy">' + (x.cot ? esc(x.cot.join(', ')) : '–') + '</td>' +
          '<td><a class="dl-btn" href="' + esc(url) + '"' + (x.dinh_dang === 'csv' ? ' download' : '') + '>' + esc(x.dinh_dang.toUpperCase()) + '</a></td></tr>';
      }).join('');
    }).catch(function(){ fail(dlPage); });
  }

  // =====================================================================
  // TỰ TẢI LẠI KHI CÓ DỮ LIỆU MỚI (2 phút kiểm tra một lần, chỉ khi tab đang được xem)
  // =====================================================================
  var dungDuLieu = document.querySelector('#mktChart, #etfTable, #etfDetail, #homeEtf, #holdPage, #ptPage, #dlPage, #recPage');
  if(dungDuLieu){
    var toast = null;
    function banDangThaoTac(){
      var ov = document.getElementById('smOverlay');
      var a = document.activeElement;
      return (ov && !ov.hidden) || (a && (a.tagName === 'INPUT' || a.tagName === 'SELECT' || a.tagName === 'TEXTAREA'));
    }
    function taiLai(){
      try{ sessionStorage.setItem('kcn-cuon', String(window.scrollY)); }catch(e){}
      location.reload();
    }
    function baoCoDuLieuMoi(luc){
      if(!toast){
        toast = document.createElement('div');
        toast.className = 'kcn-toast';
        toast.setAttribute('role', 'status');
        document.body.appendChild(toast);
      }
      toast.innerHTML = '<span>Có dữ liệu mới lúc ' + esc(luc.slice(11)) + '</span><button type="button">Cập nhật</button>';
      toast.querySelector('button').onclick = taiLai;
      toast.hidden = false;
    }
    function kiemTra(){
      if(document.visibilityState !== 'visible') return;
      Promise.all([phienHienTai, docPhien()]).then(function(v){
        if(!v[1] || v[1] === v[0]) return;
        if(window.KCN_lamMoi){
          phienHienTai = Promise.resolve(v[1]);
          window.KCN_lamMoi();
        }else if(banDangThaoTac()) baoCoDuLieuMoi(v[1]);
        else taiLai();
      });
    }
    setInterval(kiemTra, 120000);
    document.addEventListener('visibilitychange', kiemTra);
    // khôi phục vị trí cuộn sau khi tự tải lại
    try{
      var cuon = sessionStorage.getItem('kcn-cuon');
      if(cuon !== null){
        sessionStorage.removeItem('kcn-cuon');
        window.addEventListener('load', function(){ setTimeout(function(){ window.scrollTo(0, Number(cuon)); }, 300); });
      }
    }catch(e){}
  }
})();
