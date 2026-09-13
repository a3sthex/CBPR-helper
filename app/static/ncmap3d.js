/* P-Map 3D: собственный компактный WebGL-движок карты Найт-Сити (без сторонних
   библиотек). Рисует стилизованную голограмму города: земля, районы, объёмные
   кварталы, светящиеся магистрали, подписи и билборды-маркеры. Управление:
   тянуть мышью — перемещение карты (как в городских картах), Shift или правая
   кнопка — поворот/наклон, колесо — зум, кнопки +/−/⟲. */
(function () {
  'use strict';

  // ---------- мини-матрицы (column-major, как в WebGL) ----------
  function m4Persp(fovy, aspect, near, far) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
    return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
  }
  function m4LookAt(eye, c, up) {
    let z = [eye[0] - c[0], eye[1] - c[1], eye[2] - c[2]];
    let zl = Math.hypot(z[0], z[1], z[2]) || 1; z = z.map(v => v / zl);
    let x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]];
    let xl = Math.hypot(x[0], x[1], x[2]) || 1; x = x.map(v => v / xl);
    const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
      -(x[0] * eye[0] + x[1] * eye[1] + x[2] * eye[2]),
      -(y[0] * eye[0] + y[1] * eye[1] + y[2] * eye[2]),
      -(z[0] * eye[0] + z[1] * eye[1] + z[2] * eye[2]), 1];
  }
  function m4Mul(a, b) {
    const o = new Array(16);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
      o[j * 4 + i] = a[i] * b[j * 4] + a[4 + i] * b[j * 4 + 1] + a[8 + i] * b[j * 4 + 2] + a[12 + i] * b[j * 4 + 3];
    }
    return o;
  }
  function m4Inv(m) {
    const o = new Array(16);
    const a00 = m[0], a01 = m[1], a02 = m[2], a03 = m[3], a10 = m[4], a11 = m[5], a12 = m[6], a13 = m[7],
      a20 = m[8], a21 = m[9], a22 = m[10], a23 = m[11], a30 = m[12], a31 = m[13], a32 = m[14], a33 = m[15];
    const b00 = a00 * a11 - a01 * a10, b01 = a00 * a12 - a02 * a10, b02 = a00 * a13 - a03 * a10,
      b03 = a01 * a12 - a02 * a11, b04 = a01 * a13 - a03 * a11, b05 = a02 * a13 - a03 * a12,
      b06 = a20 * a31 - a21 * a30, b07 = a20 * a32 - a22 * a30, b08 = a20 * a33 - a23 * a30,
      b09 = a21 * a32 - a22 * a31, b10 = a21 * a33 - a23 * a31, b11 = a22 * a33 - a23 * a32;
    let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
    if (!det) return null;
    det = 1 / det;
    o[0] = (a11 * b11 - a12 * b10 + a13 * b09) * det; o[1] = (a02 * b10 - a01 * b11 - a03 * b09) * det;
    o[2] = (a31 * b05 - a32 * b04 + a33 * b03) * det; o[3] = (a22 * b04 - a21 * b05 - a23 * b03) * det;
    o[4] = (a12 * b08 - a10 * b11 - a13 * b07) * det; o[5] = (a00 * b11 - a02 * b08 + a03 * b07) * det;
    o[6] = (a32 * b02 - a30 * b05 - a33 * b01) * det; o[7] = (a20 * b05 - a22 * b02 + a23 * b01) * det;
    o[8] = (a10 * b10 - a11 * b08 + a13 * b06) * det; o[9] = (a01 * b08 - a00 * b10 - a03 * b06) * det;
    o[10] = (a30 * b04 - a31 * b02 + a33 * b00) * det; o[11] = (a21 * b02 - a20 * b04 - a23 * b00) * det;
    o[12] = (a11 * b07 - a10 * b09 - a12 * b06) * det; o[13] = (a00 * b09 - a01 * b07 + a02 * b06) * det;
    o[14] = (a31 * b01 - a30 * b03 - a32 * b00) * det; o[15] = (a20 * b03 - a21 * b01 + a22 * b00) * det;
    return o;
  }

  // ---------- геометрия ----------
  function samplePath(d) {
    const vals = (d.match(/[MLCZ]|-?\d+(?:\.\d+)?/g) || []);
    const polys = []; let pts = []; let i = 0;
    while (i < vals.length) {
      const t = vals[i];
      if (t === 'M' || t === 'L') { pts.push([+vals[i + 1], +vals[i + 2]]); i += 3; }
      else if (t === 'C') {
        const [x0, y0] = pts[pts.length - 1];
        const [x1, y1, x2, y2, x3, y3] = vals.slice(i + 1, i + 7).map(Number);
        for (let s = 1; s <= 24; s++) {
          const u = s / 24;
          pts.push([(1 - u) ** 3 * x0 + 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u ** 3 * x3,
            (1 - u) ** 3 * y0 + 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u ** 3 * y3]);
        }
        i += 7;
      } else if (t === 'Z') { polys.push(pts); pts = []; i += 1; } else i += 1;
    }
    if (pts.length) polys.push(pts);
    return polys;
  }
  function pointInPoly(poly, x, y) {
    let ok = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) ok = !ok;
    }
    return ok;
  }
  function earClip(pts) {
    const area2 = pts.reduce((s, p, i) => { const q = pts[(i + 1) % pts.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0);
    const list = (area2 > 0 ? pts : pts.slice().reverse()).map((_, i) => i);
    const P = area2 > 0 ? pts : pts.slice().reverse();
    const tris = [];
    let guard = 0;
    const seq = list.slice();
    while (seq.length > 3 && guard++ < 4000) {
      let ear = -1;
      for (let i = 0; i < seq.length; i++) {
        const a = seq[(i + seq.length - 1) % seq.length], b = seq[i], c = seq[(i + 1) % seq.length];
        const cross = (P[b][0] - P[a][0]) * (P[c][1] - P[a][1]) - (P[b][1] - P[a][1]) * (P[c][0] - P[a][0]);
        if (cross <= 0) continue;
        let inside = false;
        for (const k of seq) {
          if (k === a || k === b || k === c) continue;
          if (pointInPoly([P[a], P[b], P[c]], P[k][0], P[k][1])) { inside = true; break; }
        }
        if (!inside) { ear = i; break; }
      }
      if (ear < 0) break;
      const a = seq[(ear + seq.length - 1) % seq.length], b = seq[ear], c = seq[(ear + 1) % seq.length];
      tris.push([a, b, c]);
      seq.splice(ear, 1);
    }
    if (seq.length === 3) tris.push([seq[0], seq[1], seq[2]]);
    return tris;
  }

  // ---------- движок ----------
  const VERT_SOLID = `
    attribute vec3 aPos; attribute vec3 aColor; attribute float aEmis;
    uniform mat4 uMVP; varying vec3 vColor; varying float vEmis; varying vec3 vNormal;
    attribute vec3 aNormal;
    void main(){ gl_Position = uMVP * vec4(aPos, 1.0); vColor = aColor; vEmis = aEmis; vNormal = aNormal; }`;
  const FRAG_SOLID = `
    precision mediump float; varying vec3 vColor; varying float vEmis; varying vec3 vNormal;
    void main(){
      vec3 n = normalize(vNormal);
      float light = 0.62 + 0.38 * max(dot(n, normalize(vec3(0.35, 0.85, 0.4))), 0.0);
      vec3 col = mix(vColor * light, vColor, vEmis);
      gl_FragColor = vec4(col, 1.0);
    }`;
  const VERT_TEX = `
    attribute vec3 aPos; attribute vec2 aUV; uniform mat4 uMVP; varying vec2 vUV;
    void main(){ gl_Position = uMVP * vec4(aPos, 1.0); vUV = aUV; }`;
  const FRAG_TEX = `
    precision mediump float; varying vec2 vUV; uniform sampler2D uTex;
    void main(){ vec4 t = texture2D(uTex, vUV); if (t.a < 0.06) discard; gl_FragColor = t; }`;

  function compile(gl, type, src) {
    const sh = gl.createShader(type); gl.shaderSource(sh, src); gl.compileShader(sh);
    return sh;
  }
  function program(gl, vs, fs) {
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    return p;
  }
  function readVar(stage, name, fallback) {
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;width:0;height:0;color:' + 'var(' + name + ',' + fallback + ')';
    stage.appendChild(probe);
    const value = getComputedStyle(probe).color;
    probe.remove();
    const m = value.match(/([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)/);
    return m ? [+m[1] / 255, +m[2] / 255, +m[3] / 255] : hex(fallback);
  }
  function hex(h) {
    h = (h || '#888').replace('#', '');
    return [parseInt(h.slice(0, 2), 16) / 255, parseInt(h.slice(2, 4), 16) / 255, parseInt(h.slice(4, 6), 16) / 255];
  }
  function mixc(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }

  const mounted = new Map();

  function buildScene(stage) {
    const geo = (typeof NC_MAP_GEOMETRY !== 'undefined') ? NC_MAP_GEOMETRY : {};
    const colors = (typeof NC_MAP_DISTRICT_COLORS !== 'undefined') ? NC_MAP_DISTRICT_COLORS : {};
    const v = { pos: [], col: [], nor: [], emis: [] };
    function push(x, y, z, c, e, n) {
      v.pos.push(x, y, z); v.col.push(c[0], c[1], c[2]); v.nor.push(n[0], n[1], n[2]); v.emis.push(e);
    }
    function tri(a, b, c, col, emis, n) {
      push(a[0], a[1], a[2], col, emis, n); push(b[0], b[1], b[2], col, emis, n); push(c[0], c[1], c[2], col, emis, n);
    }
    function quadY(a, b, c, d, y, col, emis) {
      tri([a[0], y, a[1]], [b[0], y, b[1]], [c[0], y, c[1]], col, emis, [0, 1, 0]);
      tri([a[0], y, a[1]], [c[0], y, c[1]], [d[0], y, d[1]], col, emis, [0, 1, 0]);
    }
    function ribbon(poly, y, width, col, emis) {
      for (let i = 0; i < poly.length - 1; i++) {
        const [x1, z1] = poly[i], [x2, z2] = poly[i + 1];
        const dx = x2 - x1, dz = z2 - z1; const len = Math.hypot(dx, dz) || 1;
        const px = -dz / len * width / 2, pz = dx / len * width / 2;
        quadY([x1 - px, z1 - pz], [x1 + px, z1 + pz], [x2 + px, z2 + pz], [x2 - px, z2 - pz], y, col, emis);
      }
    }
    function prism(corners, y0, y1, colSide, colTop) {
      for (let i = 0; i < 4; i++) {
        const a = corners[i], b = corners[(i + 1) % 4];
        const dx = b[0] - a[0], dz = b[1] - a[1]; const len = Math.hypot(dx, dz) || 1;
        const n = [dz / len, 0, -dx / len];
        tri([a[0], y0, a[1]], [a[0], y1, a[1]], [b[0], y1, b[1]], colSide, 0, n);
        tri([a[0], y0, a[1]], [b[0], y1, b[1]], [b[0], y0, b[1]], colSide, 0, n);
      }
      tri([corners[0][0], y1, corners[0][1]], [corners[1][0], y1, corners[1][1]], [corners[2][0], y1, corners[2][1]], colTop, 0, [0, 1, 0]);
      tri([corners[0][0], y1, corners[0][1]], [corners[2][0], y1, corners[2][1]], [corners[3][0], y1, corners[3][1]], colTop, 0, [0, 1, 0]);
    }
    function box(x1, z1, x2, z2, y0, y1, colSide, colTop) {
      const n = [[1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1]];
      tri([x2, y0, z1], [x2, y1, z1], [x2, y1, z2], colSide, 0, n[0]); tri([x2, y0, z1], [x2, y1, z2], [x2, y0, z2], colSide, 0, n[0]);
      tri([x1, y0, z2], [x1, y1, z2], [x1, y1, z1], colSide, 0, n[1]); tri([x1, y0, z2], [x1, y1, z1], [x1, y0, z1], colSide, 0, n[1]);
      tri([x1, y0, z2], [x1, y1, z2], [x2, y1, z2], colSide, 0, n[2]); tri([x1, y0, z2], [x2, y1, z2], [x2, y0, z2], colSide, 0, n[2]);
      tri([x2, y0, z1], [x2, y1, z1], [x1, y1, z1], colSide, 0, n[3]); tri([x2, y0, z1], [x1, y1, z1], [x1, y0, z1], colSide, 0, n[3]);
      tri([x1, y1, z1], [x1, y1, z2], [x2, y1, z2], colTop, 0, [0, 1, 0]); tri([x1, y1, z1], [x2, y1, z2], [x2, y1, z1], colTop, 0, [0, 1, 0]);
    }
    return { v, geo, colors, tri, quadY, ribbon, box, prism };
  }

  function mount(stage) {
    if (mounted.has(stage)) { refresh(stage); return mounted.get(stage); }
    const canvas = document.createElement('canvas');
    canvas.className = 'nc-map-3d';
    stage.appendChild(canvas);
    const gl = canvas.getContext('webgl', { antialias: true, alpha: false });
    if (!gl) { canvas.remove(); return null; }
    const progS = program(gl, VERT_SOLID, FRAG_SOLID);
    const progT = program(gl, VERT_TEX, FRAG_TEX);
    const st = {
      stage, canvas, gl, progS, progT,
      az: 0, pitch: 0.95, dist: 1250, tx: 520, tz: 470, dirty: true,
      markers: [], labels: [], texCache: new Map(),
    };
    mounted.set(stage, st);

    const bufS = gl.createBuffer();
    const bufT = gl.createBuffer();
    st.bufS = bufS; st.bufT = bufT;

    rebuildGeometry(st);
    bindControls(st);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => { st.dirty = true; }) : null;
    if (ro) ro.observe(stage);
    st.ro = ro;
    requestAnimationFrame(() => frame(st));
    return st;
  }

  function palette(st) {
    const s = st.stage;
    return {
      water: readVar(s, '--map-water', '#03060c'),
      land: readVar(s, '--map-land', '#0a0e15'),
      district: readVar(s, '--map-district', '#0d1119'),
      block: readVar(s, '--map-block', '#6f6a60'),
      road: readVar(s, '--map-road', '#28d7e6'),
      roadCore: readVar(s, '--map-road-core', '#d9fbff'),
      street: readVar(s, '--map-street', '#c9d2da'),
      label: readVar(s, '--map-label', '#ffd500'),
      park: readVar(s, '--map-park', '#16301e'),
      bd: id => readVar(s, '--map-bd-' + id, '#8fa0b0'),
    };
  }

  function rebuildGeometry(st) {
    const B = buildScene(st.stage);
    const pal = palette(st);
    st.pal = pal;
    // вода и земля
    B.quadY([-300, -300], [1300, -300], [1300, 1300], [-300, 1300], -3, pal.water, 0.35);
    for (const d of [NC_MAP_LAND].concat(NC_MAP_ISLANDS)) {
      for (const poly of samplePath(d)) {
        for (const t of earClip(poly)) {
          B.tri([poly[t[0]][0], 0, poly[t[0]][1]], [poly[t[1]][0], 0, poly[t[1]][1]], [poly[t[2]][0], 0, poly[t[2]][1]], pal.land, 0, [0, 1, 0]);
        }
      }
    }
    // районы: подложка, контур, кварталы
    let seed = 7;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    for (const id of Object.keys(B.geo)) {
      const poly = B.geo[id];
      const bd = pal.bd(id);
      for (const t of earClip(poly)) {
        B.tri([poly[t[0]][0], 0.6, poly[t[0]][1]], [poly[t[1]][0], 0.6, poly[t[1]][1]], [poly[t[2]][0], 0.6, poly[t[2]][1]], mixc(pal.district, bd, 0.10), 0, [0, 1, 0]);
      }
      const ring = poly.concat([poly[0]]);
      B.ribbon(ring, 0.9, 2.4, bd, 0.85);
      const bs = (typeof NC_MAP_BUILDINGS !== 'undefined' && NC_MAP_BUILDINGS[id]) || [];
      const tall = (id === 'city-center' || id === 'watson') ? 1.5 : 1;
      for (const b of bs) {
        const h = b[8] * tall;
        const shade = 0.7 + (((b[0] * 7 + b[1] * 13) | 0) % 10) / 18;
        B.prism([[b[0], b[1]], [b[2], b[3]], [b[4], b[5]], [b[6], b[7]]], 0.6, h,
          [pal.block[0] * shade * 0.5, pal.block[1] * shade * 0.5, pal.block[2] * shade * 0.5],
          [pal.block[0] * shade * 0.85, pal.block[1] * shade * 0.85, pal.block[2] * shade * 0.85]);
      }
    }
    // парки и проспекты
    for (const park of NC_MAP_PARKS) {
      for (const t of earClip(park)) {
        B.tri([park[t[0]][0], 0.8, park[t[0]][1]], [park[t[1]][0], 0.8, park[t[1]][1]], [park[t[2]][0], 0.8, park[t[2]][1]], pal.park, 0, [0, 1, 0]);
      }
    }
    for (const id of Object.keys(NC_MAP_AVENUES)) {
      const poly = NC_MAP_GEOMETRY[id];
      for (const line of NC_MAP_AVENUES[id]) {
        const segs = [];
        const steps = 14;
        for (let i = 0; i < steps; i++) {
          const t1 = i / steps, t2 = (i + 1) / steps;
          const x1 = line[0] + (line[2] - line[0]) * t1, z1 = line[1] + (line[3] - line[1]) * t1;
          const x2 = line[0] + (line[2] - line[0]) * t2, z2 = line[1] + (line[3] - line[1]) * t2;
          if (pointInPoly(poly, (x1 + x2) / 2, (z1 + z2) / 2)) segs.push([x1, z1], [x2, z2]);
        }
        for (let i = 0; i < segs.length; i += 2) B.ribbon([segs[i], segs[i + 1]], 1.0, 2.4, pal.street, 0.3);
      }
    }
    // дороги
    for (const d of NC_MAP_STREETS) for (const poly of samplePath(d)) B.ribbon(poly, 1.1, 1.6, pal.street, 0.25);
    for (const d of NC_MAP_ROADS) for (const poly of samplePath(d)) B.ribbon(poly, 1.3, 5, pal.road, 1);
    for (const d of NC_MAP_ROADS) for (const poly of samplePath(d)) B.ribbon(poly, 1.5, 1.6, pal.roadCore, 1);
    for (const d of NC_MAP_BADLANDS_ROADS) for (const poly of samplePath(d)) B.ribbon(poly, 1.1, 2, pal.road, 0.8);

    const gl = st.gl;
    const n = B.v.pos.length / 3;
    const inter = new Float32Array(n * 10);
    for (let i = 0; i < n; i++) {
      inter[i * 10] = B.v.pos[i * 3]; inter[i * 10 + 1] = B.v.pos[i * 3 + 1]; inter[i * 10 + 2] = B.v.pos[i * 3 + 2];
      inter[i * 10 + 3] = B.v.col[i * 3]; inter[i * 10 + 4] = B.v.col[i * 3 + 1]; inter[i * 10 + 5] = B.v.col[i * 3 + 2];
      inter[i * 10 + 6] = B.v.nor[i * 3]; inter[i * 10 + 7] = B.v.nor[i * 3 + 1]; inter[i * 10 + 8] = B.v.nor[i * 3 + 2];
      inter[i * 10 + 9] = B.v.emis[i];
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, st.bufS);
    gl.bufferData(gl.ARRAY_BUFFER, inter, gl.STATIC_DRAW);
    st.solidCount = n;
    st.dirty = true;
  }

  function labelTexture(st, text, color, big) {
    const key = text + '|' + color.join(',') + '|' + big;
    if (st.texCache.has(key)) return st.texCache.get(key);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const font = (big ? 64 : 40) + 'px Orbitron, sans-serif';
    ctx.font = 'bold ' + font;
    const w = Math.ceil(ctx.measureText(text).width) + 40;
    canvas.width = Math.max(64, w); canvas.height = big ? 96 : 64;
    const c2 = canvas.getContext('2d');
    c2.font = 'bold ' + font;
    c2.textAlign = 'center'; c2.textBaseline = 'middle';
    c2.lineWidth = 10; c2.strokeStyle = 'rgba(4,7,13,.9)';
    c2.strokeText(text, canvas.width / 2, canvas.height / 2);
    c2.fillStyle = 'rgb(' + color.map(x => Math.round(x * 255)).join(',') + ')';
    c2.fillText(text, canvas.width / 2, canvas.height / 2);
    const tex = st.gl.createTexture();
    st.gl.bindTexture(st.gl.TEXTURE_2D, tex);
    st.gl.texImage2D(st.gl.TEXTURE_2D, 0, st.gl.RGBA, st.gl.RGBA, st.gl.UNSIGNED_BYTE, canvas);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_MIN_FILTER, st.gl.LINEAR);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_WRAP_S, st.gl.CLAMP_TO_EDGE);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_WRAP_T, st.gl.CLAMP_TO_EDGE);
    const rec = { tex, aspect: canvas.width / canvas.height };
    st.texCache.set(key, rec);
    return rec;
  }

  function markerTexture(st, rec) {
    const key = 'm' + rec.kind + '|' + rec.text;
    if (st.texCache.has(key)) return st.texCache.get(key);
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 96;
    const c = canvas.getContext('2d');
    const stroke = rec.kind === 'contracts' ? 'rgb(255,213,0)' : rec.kind === 'poi' ? 'rgb(0,229,255)' : 'rgb(255,213,0)';
    c.beginPath(); c.arc(48, 48, 34, 0, Math.PI * 2);
    c.fillStyle = 'rgba(5,8,14,.92)'; c.fill();
    c.lineWidth = 8; c.strokeStyle = stroke; c.stroke();
    c.fillStyle = stroke; c.font = 'bold 44px Orbitron, sans-serif';
    c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(rec.text, 48, 52);
    const tex = st.gl.createTexture();
    st.gl.bindTexture(st.gl.TEXTURE_2D, tex);
    st.gl.texImage2D(st.gl.TEXTURE_2D, 0, st.gl.RGBA, st.gl.RGBA, st.gl.UNSIGNED_BYTE, canvas);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_MIN_FILTER, st.gl.LINEAR);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_WRAP_S, st.gl.CLAMP_TO_EDGE);
    st.gl.texParameteri(st.gl.TEXTURE_2D, st.gl.TEXTURE_WRAP_T, st.gl.CLAMP_TO_EDGE);
    const out = { tex, aspect: 1 };
    st.texCache.set(key, out);
    return out;
  }

  function readMarkers(st) {
    const list = [];
    st.stage.querySelectorAll('.nc-map-overlay .nc-marker').forEach(el => {
      const m = /translate\(([-\d.]+) ([-\d.]+)\)/.exec(el.getAttribute('transform') || '');
      if (!m) return;
      const kind = el.classList.contains('nc-layer-contracts') ? 'contracts'
        : el.classList.contains('nc-layer-poi') ? 'poi'
          : el.classList.contains('nc-layer-vendors') ? 'vendors' : 'contracts';
      const text = (el.querySelector('text') || {}).textContent || '•';
      list.push({ x: +m[1], z: +m[2], kind, text, el });
    });
    st.markers = list;
  }

  function readLabels(st) {
    const list = [];
    if (typeof NC_DISTRICTS === 'undefined') return list;
    for (const d of NC_DISTRICTS) {
      const a = (typeof NC_MAP_COORDS !== 'undefined' && NC_MAP_COORDS[d.id]) || [500, 500];
      const name = (typeof T === 'function') ? T(d.en, d.ru) : d.en;
      list.push({ x: a[0], z: a[1], text: name, big: true, color: st.pal.bd(d.id) });
    }
    st.labels = list;
  }

  function camera(st) {
    const target = [st.tx == null ? 520 : st.tx, 0, st.tz == null ? 470 : st.tz];
    const cp = Math.cos(st.pitch), sp = Math.sin(st.pitch);
    const eye = [target[0] + st.dist * cp * Math.sin(st.az), st.dist * sp, target[2] + st.dist * cp * Math.cos(st.az)];
    const view = m4LookAt(eye, target, [0, 1, 0]);
    const aspect = (st.canvas.clientWidth || 1) / (st.canvas.clientHeight || 1);
    const proj = m4Persp(0.9, aspect, 10, 6000);
    return { view, proj, mvp: m4Mul(proj, view), eye };
  }

  function frame(st) {
    if (!mounted.has(st.stage)) return;
    if (st.dirty) { st.dirty = false; draw(st); }
    requestAnimationFrame(() => frame(st));
  }

  function draw(st) {
    const gl = st.gl;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(2, Math.floor(st.canvas.clientWidth * dpr));
    const h = Math.max(2, Math.floor(st.canvas.clientHeight * dpr));
    if (st.canvas.width !== w || st.canvas.height !== h) { st.canvas.width = w; st.canvas.height = h; }
    gl.viewport(0, 0, w, h);
    gl.clearColor(st.pal.water[0], st.pal.water[1], st.pal.water[2], 1);
    gl.enable(gl.DEPTH_TEST);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const cam = camera(st);

    gl.useProgram(st.progS);
    gl.bindBuffer(gl.ARRAY_BUFFER, st.bufS);
    const stride = 10 * 4;
    const aPos = gl.getAttribLocation(st.progS, 'aPos');
    const aColor = gl.getAttribLocation(st.progS, 'aColor');
    const aNor = gl.getAttribLocation(st.progS, 'aNormal');
    const aEmis = gl.getAttribLocation(st.progS, 'aEmis');
    gl.enableVertexAttribArray(aPos); gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, stride, 0);
    gl.enableVertexAttribArray(aColor); gl.vertexAttribPointer(aColor, 3, gl.FLOAT, false, stride, 12);
    gl.enableVertexAttribArray(aNor); gl.vertexAttribPointer(aNor, 3, gl.FLOAT, false, stride, 24);
    gl.enableVertexAttribArray(aEmis); gl.vertexAttribPointer(aEmis, 1, gl.FLOAT, false, stride, 36);
    gl.uniformMatrix4fv(gl.getUniformLocation(st.progS, 'uMVP'), false, cam.mvp);
    gl.drawArrays(gl.TRIANGLES, 0, st.solidCount);

    // прозрачный слой: подписи на земле + билборды-маркеры
    readMarkers(st);
    readLabels(st);
    const quads = [];
    for (const lab of st.labels) {
      const rec = labelTexture(st, lab.text, lab.color, lab.big);
      const hWorld = lab.big ? 34 : 20;
      const wWorld = hWorld * rec.aspect;
      quads.push({ rec, uvs: [[0, 0], [1, 0], [1, 1], [0, 1]], corners: [[lab.x - wWorld / 2, 2, lab.z - hWorld / 2], [lab.x + wWorld / 2, 2, lab.z - hWorld / 2], [lab.x + wWorld / 2, 2, lab.z + hWorld / 2], [lab.x - wWorld / 2, 2, lab.z + hWorld / 2]], depth: dist2(cam.eye, [lab.x, 2, lab.z]) });
    }
    const right = [cam.view[0], cam.view[4], cam.view[8]];
    const up = [cam.view[1], cam.view[5], cam.view[9]];
    for (const mk of st.markers) {
      const rec = markerTexture(st, mk);
      const size = mk.kind === 'contracts' ? 34 : 26;
      const cx = mk.x, cy = size / 2 + 4, cz = mk.z;
      quads.push({
        rec, depth: dist2(cam.eye, [cx, cy, cz]),
        corners: [
          [cx - right[0] * size / 2 - up[0] * size / 2, cy - right[1] * size / 2 - up[1] * size / 2, cz - right[2] * size / 2 - up[2] * size / 2],
          [cx + right[0] * size / 2 - up[0] * size / 2, cy + right[1] * size / 2 - up[1] * size / 2, cz + right[2] * size / 2 - up[2] * size / 2],
          [cx + right[0] * size / 2 + up[0] * size / 2, cy + right[1] * size / 2 + up[1] * size / 2, cz + right[2] * size / 2 + up[2] * size / 2],
          [cx - right[0] * size / 2 + up[0] * size / 2, cy - right[1] * size / 2 + up[1] * size / 2, cz - right[2] * size / 2 + up[2] * size / 2],
        ],
      });
    }
    quads.sort((a, b) => b.depth - a.depth);
    const data = [];
    const uvs = [[0, 1], [1, 1], [1, 0], [0, 0]];
    const idx = [];
    for (const q of quads) {
      const base = data.length / 5;
      const quv = q.uvs || uvs;
      for (let i = 0; i < 4; i++) data.push(q.corners[i][0], q.corners[i][1], q.corners[i][2], quv[i][0], quv[i][1]);
      idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
      q._tex = q.rec.tex;
    }
    // рисуем пакетами по текстурам
    gl.useProgram(st.progT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    gl.bindBuffer(gl.ARRAY_BUFFER, st.bufT);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.DYNAMIC_DRAW);
    const tPos = gl.getAttribLocation(st.progT, 'aPos');
    const tUV = gl.getAttribLocation(st.progT, 'aUV');
    gl.enableVertexAttribArray(tPos); gl.vertexAttribPointer(tPos, 3, gl.FLOAT, false, 20, 0);
    gl.enableVertexAttribArray(tUV); gl.vertexAttribPointer(tUV, 2, gl.FLOAT, false, 20, 12);
    gl.uniformMatrix4fv(gl.getUniformLocation(st.progT, 'uMVP'), false, cam.mvp);
    gl.uniform1i(gl.getUniformLocation(st.progT, 'uTex'), 0);
    // группировка: сортируем уже по глубине; меняем текстуру по мере необходимости
    let current = null;
    let start = 0;
    const flush = (from, to, tex) => {
      if (to <= from) return;
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.drawElements(gl.TRIANGLES, (to - from) * 6, gl.UNSIGNED_SHORT, from * 6 * 2);
    };
    if (!st.idxBuf) st.idxBuf = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, st.idxBuf);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(idx), gl.DYNAMIC_DRAW);
    for (let i = 0; i <= quads.length; i++) {
      const tex = i < quads.length ? quads[i]._tex : null;
      if (tex !== current) { flush(start, i, current); current = tex; start = i; }
    }
    gl.depthMask(true);
    gl.disable(gl.BLEND);
  }

  function dist2(a, b) { const dx = a[0] - b[0], dy = a[1] - b[1], dz = a[2] - b[2]; return dx * dx + dy * dy + dz * dz; }

  function bindControls(st) {
    const stage = st.stage;
    let drag = false, lx = 0, ly = 0;
    const cx0 = () => (st.tx == null ? 520 : st.tx), cz0 = () => (st.tz == null ? 470 : st.tz);
    st.onDown = e => {
      if (e.button !== 0 && e.button !== 2) return;
      drag = (e.shiftKey || e.button === 2) ? 'orbit' : 'pan';
      lx = e.clientX; ly = e.clientY; st.downX = e.clientX; st.downY = e.clientY;
    };
    st.onMove = e => {
      if (!drag) return;
      const dx = e.clientX - lx, dy = e.clientY - ly;
      lx = e.clientX; ly = e.clientY;
      if (drag === 'orbit') {
        st.az -= dx * 0.005;
        st.pitch = Math.min(1.45, Math.max(0.25, st.pitch + dy * 0.004));
      } else {
        // панорамирование: содержимое следует за курсором, цель ограничена картой
        const cam = camera(st);
        const s = st.dist * 0.0011;
        const rx = cam.view[0], rz = cam.view[8];
        let fx = cx0() - cam.eye[0], fz = cz0() - cam.eye[2];
        const fl = Math.hypot(fx, fz) || 1; fx /= fl; fz /= fl;
        st.tx = Math.min(1500, Math.max(-300, cx0() - rx * dx * s + fx * dy * s));
        st.tz = Math.min(1500, Math.max(-300, cz0() - rz * dx * s + fz * dy * s));
      }
      st.dirty = true;
    };
    st.onUp = () => { drag = false; };
    st.onCtx = e => { e.preventDefault(); };
    st.onWheel = e => { e.preventDefault(); st.dist = Math.min(2600, Math.max(350, st.dist * (e.deltaY < 0 ? 0.9 : 1.1))); st.dirty = true; };
    st.onClick = e => {
      if (st.downX != null && Math.hypot(e.clientX - st.downX, e.clientY - st.downY) > 6) return; // это было вращение, не клик
      const pick = pickMarker(st, e);
      if (pick) pick.el.click();
    };
    stage.addEventListener('mousedown', st.onDown);
    stage.addEventListener('contextmenu', st.onCtx);
    window.addEventListener('mousemove', st.onMove);
    window.addEventListener('mouseup', st.onUp);
    stage.addEventListener('wheel', st.onWheel, { passive: false });
    stage.addEventListener('click', st.onClick);
    // кнопки зума 3D
    const mk = (label, fn, top) => {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'nc-map-zoom-btn nc-map-3d-btn'; b.textContent = label;
      b.style.cssText = 'position:absolute;z-index:6;left:10px;width:32px;height:32px;top:' + top + 'px;font:bold 15px Orbitron;background:color-mix(in srgb,var(--panel) 88%,transparent);backdrop-filter:blur(6px);border:1px solid var(--line);color:var(--text);cursor:pointer';
      b.onclick = () => { fn(); st.dirty = true; };
      stage.appendChild(b);
      st.buttons = (st.buttons || []).concat(b);
      return b;
    };
    mk('+', () => { st.dist = Math.max(350, st.dist * 0.8); }, 10);
    mk('−', () => { st.dist = Math.min(2600, st.dist * 1.25); }, 46);
    mk('⟲', () => { st.az = 0; st.pitch = 0.95; st.dist = 1250; st.tx = 520; st.tz = 470; }, 82);
    const hint = document.createElement('div');
    hint.className = 'nc-map-3d-hint';
    st.hintSet = () => { hint.textContent = (typeof T === 'function') ? T('Drag — move map, Shift or right button — rotate and tilt, wheel — zoom', 'Тяните мышью — перемещение карты, Shift или правая кнопка — поворот и наклон, колесо — масштаб') : 'Drag — move, Shift/right-drag — rotate, wheel — zoom'; };
    st.hintSet();
    stage.appendChild(hint);
    st.hint = hint;
  }

  function pickMarker(st, e) {
    const rect = st.canvas.getBoundingClientRect();
    const nx = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const ny = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    const cam = camera(st);
    const inv = m4Inv(cam.mvp);
    if (!inv) return null;
    const tp = (x, y, z) => {
      const w = inv[3] * x + inv[7] * y + inv[11] * z + inv[15];
      return [(inv[0] * x + inv[4] * y + inv[8] * z + inv[12]) / w,
        (inv[1] * x + inv[5] * y + inv[9] * z + inv[13]) / w,
        (inv[2] * x + inv[6] * y + inv[10] * z + inv[14]) / w];
    };
    const p0 = tp(nx, ny, -1), p1 = tp(nx, ny, 1);
    const dir = [p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]];
    if (Math.abs(dir[1]) < 1e-6) return null;
    const t = (0 - p0[1]) / dir[1];
    if (t < 0) return null;
    const hx = p0[0] + dir[0] * t, hz = p0[2] + dir[2] * t;
    let best = null, bestD = 40 * 40;
    for (const mk of st.markers) {
      const d = (mk.x - hx) ** 2 + (mk.z - hz) ** 2;
      if (d < bestD) { bestD = d; best = mk; }
    }
    return best;
  }

  function unmount(stage) {
    const st = mounted.get(stage);
    if (!st) return;
    mounted.delete(stage);
    stage.removeEventListener('mousedown', st.onDown);
    stage.removeEventListener('contextmenu', st.onCtx);
    window.removeEventListener('mousemove', st.onMove);
    window.removeEventListener('mouseup', st.onUp);
    stage.removeEventListener('wheel', st.onWheel);
    stage.removeEventListener('click', st.onClick);
    (st.buttons || []).forEach(b => b.remove());
    if (st.hint) st.hint.remove();
    if (st.ro) st.ro.disconnect();
    st.canvas.remove();
  }

  function refresh(stage) {
    const st = mounted.get(stage);
    if (!st) return;
    rebuildGeometry(st);
  }

  window.NCMap3D = {
    mount, unmount,
    refreshColors() { mounted.forEach((st, stage) => { rebuildGeometry(st); if (st.hintSet) st.hintSet(); }); },
    refresh(stage) { refresh(stage); },
  };
  // отладочные/тестовые чистые функции
  window.NCMap3DDebug = { earClip, pointInPoly, samplePath, m4Mul, m4Inv };
})();
