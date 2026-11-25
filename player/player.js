(function () {
  var video = document.getElementById('video');
  var vurl = new URLSearchParams(location.search).get('vurl');

  function showForm() {
    var wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:#e6edf3;font-family:"Microsoft YaHei",sans-serif;background:#000;padding:24px;text-align:center;';
    wrap.innerHTML = ''
      + '<div style="font-size:16px">输入 m3u8 / flv 播放地址</div>'
      + '<input id="dx-url" placeholder="https://example.com/live.m3u8" '
      + 'style="width:min(560px,90vw);padding:10px 12px;border-radius:8px;border:1px solid #2f81f7;background:#0d1620;color:#e6edf3;outline:none">'
      + '<button id="dx-play" style="padding:9px 22px;border-radius:8px;border:0;background:#2f81f7;color:#fff;cursor:pointer">播放</button>'
      + '<div style="font-size:12px;color:#7d93a5">道玄微数科技信息有限公司</div>';
    document.body.appendChild(wrap);

    var input = document.getElementById('dx-url');
    var button = document.getElementById('dx-play');
    function play() {
      var url = (input.value || '').trim();
      if (!url) {
        input.focus();
        return;
      }
      location.search = '?vurl=' + encodeURIComponent(url);
    }
    button.addEventListener('click', play);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') play();
    });
    input.focus();
  }

  if (!vurl) {
    showForm();
    return;
  }

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = vurl;
  } else if (window.Hls && Hls.isSupported()) {
    var hls = new Hls();
    hls.loadSource(vurl);
    hls.attachMedia(video);
  } else {
    video.src = vurl;
  }
})();
