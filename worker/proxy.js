/**
 * 道玄微数 · m3u8 代理 Worker
 *
 * 用法：
 *   https://<worker域名>/?url=<encodeURIComponent(源地址)>
 *
 * 作用：
 *   1. 转发请求时补 User-Agent / Referer，绕过防盗链
 *   2. 返回 Access-Control-Allow-Origin: *，解决浏览器跨域
 *   3. 自动重写 m3u8 内的分片地址，递归走代理
 *
 * 部署：Cloudflare Dashboard → Workers → 创建 → 粘贴本文件 → 部署
 */

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': '*',
  'Access-Control-Allow-Methods': 'GET,HEAD,OPTIONS',
};

function proxyUrl(origin, target) {
  return origin + '/?url=' + encodeURIComponent(target);
}

function rewritePlaylist(text, baseUrl, origin) {
  return text
    .split(/\r?\n/)
    .map((line) => {
      const trimmed = line.trim();
      if (!trimmed) return line;
      if (trimmed.startsWith('#')) {
        return line.replace(/URI="([^"]+)"/g, (_, uri) => {
          const absolute = new URL(uri, baseUrl).toString();
          return 'URI="' + proxyUrl(origin, absolute) + '"';
        });
      }
      const absolute = new URL(trimmed, baseUrl).toString();
      return proxyUrl(origin, absolute);
    })
    .join('\n');
}

export default {
  async fetch(request) {
    const requestUrl = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    const target = requestUrl.searchParams.get('url');
    if (!target) {
      return new Response('missing ?url=', { status: 400, headers: CORS });
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      return new Response('invalid url', { status: 400, headers: CORS });
    }

    const upstream = await fetch(targetUrl.toString(), {
      headers: {
        'User-Agent': UA,
        'Referer': targetUrl.origin + '/',
        'Accept': '*/*',
      },
      redirect: 'follow',
    });

    const contentType = upstream.headers.get('content-type') || '';
    const isPlaylist = contentType.includes('mpegurl')
      || targetUrl.pathname.endsWith('.m3u8')
      || targetUrl.pathname.endsWith('.m3u');

    if (isPlaylist) {
      const text = await upstream.text();
      const rewritten = rewritePlaylist(text, targetUrl.toString(), requestUrl.origin);
      return new Response(rewritten, {
        status: upstream.status,
        headers: {
          ...CORS,
          'Content-Type': 'application/vnd.apple.mpegurl',
          'Cache-Control': 'no-cache',
        },
      });
    }

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        ...CORS,
        'Content-Type': contentType || 'application/octet-stream',
      },
    });
  },
};
