/**
 * AirScribe 2.0 — Interactive AI Gesture Virtual Whiteboard
 * Next-generation touchless computer vision engine with MediaPipe Hands,
 * Bézier spline ink smoothing, live VFX particle engine, laser wand trails,
 * 5-finger telemetry sensors, and tactile Web Audio feedback.
 */

// =========================================================
// Configuration & Application State
// =========================================================
const CONFIG = {
  dwellTimeMs: 520,
  pinchThresholdNorm: 0.052,
  smoothAlphaDraw: 0.32,
  smoothAlphaHover: 0.65,
  maxHistoryStates: 30,
  wandFadeDurationMs: 1200,
  particleMaxCount: 160,
};

const STATE = {
  tool: 'pen', // 'pen', 'highlighter', 'eraser', 'line', 'rectangle', 'circle', 'arrow', 'laser', 'spotlight'
  color: '#3B5BFD', // Royal Indigo default
  size: 8,
  eraserRadius: 36,
  canvasMode: 'camera', // 'camera', 'whiteboard', 'blackboard', 'blueprint'
  gridMode: 'none',     // 'none', 'dots', 'graph', 'blueprint'
  soundEnabled: localStorage.getItem('airscribe_audio') !== 'false',

  // Coordinate smoothing & path tracking
  rawIndexTip: null,
  smoothIndexTip: null,
  prevPoint: null,
  currentStrokePoints: [], // for Bézier smoothing
  shapeStartPoint: null,
  isDrawingShape: false,

  // Gesture State
  currentGesture: 'NONE', // 'DRAW', 'SELECT', 'ERASER', 'PINCH', 'FIST'
  fingersUp: [false, false, false, false, false], // [Thumb, Index, Middle, Ring, Pinky]

  // Dwell timer
  hoveredElement: null,
  hoverStartTime: null,
  dwellProgress: 0,

  // Living Doodles & Presenter tools
  aliveDoodles: [],
  laserPoints: [],

  // History Stack
  undoStack: [],
  redoStack: [],
  strokeInProgress: false,

  // Performance Telemetry
  fps: 60,
  lastFrameTime: performance.now(),
  cameraActive: false,
};

// VFX Collections
const wandTrails = []; // array of { points: [{x,y}], color, size, bornAt }
const particles = [];  // array of { x, y, vx, vy, size, color, alpha, life, maxLife }

// =========================================================
// DOM Element References
// =========================================================
const videoElement = document.getElementById('webcamVideo');
const cameraCanvas = document.getElementById('cameraCanvas');
const gridCanvas = document.getElementById('gridCanvas');
const drawingCanvas = document.getElementById('drawingCanvas');
const previewCanvas = document.getElementById('previewCanvas');
const particleCanvas = document.getElementById('particleCanvas');
const pipCanvas = document.getElementById('pipCanvas');

const cameraCtx = cameraCanvas.getContext('2d');
const gridCtx = gridCanvas.getContext('2d');
const drawCtx = drawingCanvas.getContext('2d');
const previewCtx = previewCanvas.getContext('2d');
const particleCtx = particleCanvas.getContext('2d');
const pipCtx = pipCanvas.getContext('2d');

const virtualCursor = document.getElementById('virtualCursor');
const cursorDot = document.getElementById('cursorDot');
const cursorGlow = document.getElementById('cursorGlow');
const cursorBadge = document.getElementById('cursorBadge');
const cursorEraserRing = document.getElementById('cursorEraserRing');
const dwellFillCircle = document.getElementById('dwellFillCircle');

const toolbarWrapper = document.getElementById('toolbarWrapper');
const collapsedCapsule = document.getElementById('collapsedCapsule');
const capsuleToolLabel = document.getElementById('capsuleToolLabel');
const capsuleColorDot = document.getElementById('capsuleColorDot');
const sizePreviewDot = document.getElementById('sizePreviewDot');
const customColorInput = document.getElementById('customColorInput');

const hudGestureMode = document.getElementById('hudGestureMode');
const gestureBadgeDot = document.getElementById('gestureBadgeDot');
const hudTool = document.getElementById('hudTool');
const hudFps = document.getElementById('hudFps');
const toastBanner = document.getElementById('toastBanner');
const toastMessage = document.getElementById('toastMessage');
const toastIcon = document.getElementById('toastIcon');
const pipContainer = document.getElementById('pipContainer');
const themeModeLabel = document.getElementById('themeModeLabel');

// Finger telemetry nodes
const fingerNodes = {
  thumb: document.getElementById('fnThumb'),
  index: document.getElementById('fnIndex'),
  middle: document.getElementById('fnMiddle'),
  ring: document.getElementById('fnRing'),
  pinky: document.getElementById('fnPinky'),
};

// Guide modal
const guideModalBackdrop = document.getElementById('guideModalBackdrop');
const btnOpenGuide = document.getElementById('btnOpenGuide');
const btnCloseGuide = document.getElementById('btnCloseGuide');
const btnDismissGuide = document.getElementById('btnDismissGuide');

// Audio icons
const iconAudioOn = document.getElementById('iconAudioOn');
const iconAudioMuted = document.getElementById('iconAudioMuted');

// =========================================================
// Synthesized Web Audio Engine (Sci-Fi Tactile SFX)
// =========================================================
let audioCtx = null;

function initAudio() {
  if (!audioCtx && window.AudioContext) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
}

function playSound(type = 'click') {
  if (!STATE.soundEnabled) return;
  try {
    initAudio();
    if (!audioCtx) return;
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }

    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === 'click') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(1320, now + 0.04);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
      osc.start(now);
      osc.stop(now + 0.05);
    } else if (type === 'pinch') {
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(520, now);
      osc.frequency.exponentialRampToValueAtTime(1040, now + 0.08);
      gain.gain.setValueAtTime(0.14, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
      osc.start(now);
      osc.stop(now + 0.1);
    } else if (type === 'clear') {
      // Futuristic sweep down
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.exponentialRampToValueAtTime(120, now + 0.22);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.24);
      osc.start(now);
      osc.stop(now + 0.24);
    } else if (type === 'success') {
      // Major chord chime
      [587.33, 739.99, 880, 1174.66].forEach((freq, idx) => {
        const subOsc = audioCtx.createOscillator();
        const subGain = audioCtx.createGain();
        subOsc.connect(subGain);
        subGain.connect(audioCtx.destination);
        subOsc.frequency.setValueAtTime(freq, now + idx * 0.04);
        subGain.gain.setValueAtTime(0.08, now + idx * 0.04);
        subGain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        subOsc.start(now + idx * 0.04);
        subOsc.stop(now + 0.35);
      });
    } else if (type === 'mode') {
      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(660, now + 0.08);
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
      osc.start(now);
      osc.stop(now + 0.1);
    }
  } catch (err) {
    // Gracefully handle browser autoplay policies
  }
}

function updateAudioUI() {
  if (STATE.soundEnabled) {
    iconAudioOn.classList.remove('hidden');
    iconAudioMuted.classList.add('hidden');
  } else {
    iconAudioOn.classList.add('hidden');
    iconAudioMuted.classList.remove('hidden');
  }
  localStorage.setItem('airscribe_audio', STATE.soundEnabled ? 'true' : 'false');
}

// =========================================================
// Particle System Engine (VFX)
// =========================================================
function spawnParticles(x, y, count = 3, color = STATE.color, speed = 2.5) {
  for (let i = 0; i < count; i++) {
    if (particles.length >= CONFIG.particleMaxCount) {
      particles.shift();
    }
    const angle = Math.random() * Math.PI * 2;
    const vel = (Math.random() * 0.8 + 0.2) * speed;
    particles.push({
      x: x + (Math.random() - 0.5) * 8,
      y: y + (Math.random() - 0.5) * 8,
      vx: Math.cos(angle) * vel,
      vy: Math.sin(angle) * vel - 0.4, // gentle upward drift
      size: Math.random() * 3 + 1.5,
      color: color,
      alpha: 1.0,
      life: 0,
      maxLife: Math.floor(Math.random() * 20 + 15),
    });
  }
}

function spawnClearBurst() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  for (let i = 0; i < 75; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = Math.random() * 12 + 4;
    particles.push({
      x: w / 2,
      y: h / 2,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: Math.random() * 5 + 2,
      color: ['#00F0FF', '#FF3366', '#FFB800', '#A855F7', '#10B981'][Math.floor(Math.random() * 5)],
      alpha: 1.0,
      life: 0,
      maxLife: Math.floor(Math.random() * 30 + 20),
    });
  }
}

function updateAndRenderParticles() {
  particleCtx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);
  if (particles.length === 0) return;

  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.life++;
    p.x += p.vx;
    p.y += p.vy;
    p.alpha = 1.0 - p.life / p.maxLife;

    if (p.life >= p.maxLife || p.alpha <= 0) {
      particles.splice(i, 1);
      continue;
    }

    particleCtx.save();
    particleCtx.globalAlpha = p.alpha;
    particleCtx.fillStyle = p.color;
    particleCtx.shadowColor = p.color;
    particleCtx.shadowBlur = 8;
    particleCtx.beginPath();
    particleCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    particleCtx.fill();
    particleCtx.restore();
  }
}

// =========================================================
// Laser Wand Fading Trails Engine
// =========================================================
function updateAndRenderWandTrails() {
  if (wandTrails.length === 0 && !STATE.isDrawingShape) return;
  const now = performance.now();

  // Clear preview canvas, but remember if shape ghost preview is drawing
  if (!STATE.isDrawingShape) {
    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
  }

  for (let i = wandTrails.length - 1; i >= 0; i--) {
    const trail = wandTrails[i];
    const age = now - trail.bornAt;
    if (age >= CONFIG.wandFadeDurationMs) {
      wandTrails.splice(i, 1);
      continue;
    }

    const progress = age / CONFIG.wandFadeDurationMs;
    const alpha = Math.max(0, 1.0 - progress);

    if (trail.points.length < 2) continue;

    previewCtx.save();
    previewCtx.globalAlpha = alpha;
    previewCtx.strokeStyle = trail.color;
    previewCtx.shadowColor = trail.color;
    previewCtx.shadowBlur = 18;
    previewCtx.lineWidth = trail.size * (1.0 + (1.0 - alpha) * 0.5);
    previewCtx.lineCap = 'round';
    previewCtx.lineJoin = 'round';

    previewCtx.beginPath();
    previewCtx.moveTo(trail.points[0].x, trail.points[0].y);
    for (let j = 1; j < trail.points.length; j++) {
      previewCtx.lineTo(trail.points[j].x, trail.points[j].y);
    }
    previewCtx.stroke();
    previewCtx.restore();
  }
}

// =========================================================
// Canvas Grid Background Renderer
// =========================================================
function renderGrid() {
  const w = gridCanvas.width;
  const h = gridCanvas.height;
  gridCtx.clearRect(0, 0, w, h);

  if (STATE.gridMode === 'none') return;

  gridCtx.save();

  if (STATE.gridMode === 'dots') {
    // Subtle cyber dots
    const step = 36;
    gridCtx.fillStyle = STATE.canvasMode === 'whiteboard' ? 'rgba(0,0,0,0.18)' : 'rgba(0, 240, 255, 0.22)';
    for (let x = step / 2; x < w; x += step) {
      for (let y = step / 2; y < h; y += step) {
        gridCtx.beginPath();
        gridCtx.arc(x, y, 1.4, 0, Math.PI * 2);
        gridCtx.fill();
      }
    }
  } else if (STATE.gridMode === 'graph') {
    // Math notebook graph lines
    const step = 32;
    gridCtx.strokeStyle = STATE.canvasMode === 'whiteboard' ? 'rgba(0,0,0,0.08)' : 'rgba(255, 255, 255, 0.08)';
    gridCtx.lineWidth = 1;
    gridCtx.beginPath();
    for (let x = 0; x < w; x += step) {
      gridCtx.moveTo(x, 0);
      gridCtx.lineTo(x, h);
    }
    for (let y = 0; y < h; y += step) {
      gridCtx.moveTo(0, y);
      gridCtx.lineTo(w, y);
    }
    gridCtx.stroke();
  } else if (STATE.gridMode === 'blueprint') {
    // Futuristic cyber blueprint grid with major/minor lines
    const minorStep = 24;
    const majorStep = minorStep * 4;

    gridCtx.strokeStyle = 'rgba(0, 240, 255, 0.06)';
    gridCtx.lineWidth = 1;
    gridCtx.beginPath();
    for (let x = 0; x < w; x += minorStep) {
      gridCtx.moveTo(x, 0);
      gridCtx.lineTo(x, h);
    }
    for (let y = 0; y < h; y += minorStep) {
      gridCtx.moveTo(0, y);
      gridCtx.lineTo(w, y);
    }
    gridCtx.stroke();

    gridCtx.strokeStyle = 'rgba(0, 240, 255, 0.18)';
    gridCtx.lineWidth = 1.5;
    gridCtx.beginPath();
    for (let x = 0; x < w; x += majorStep) {
      gridCtx.moveTo(x, 0);
      gridCtx.lineTo(x, h);
    }
    for (let y = 0; y < h; y += majorStep) {
      gridCtx.moveTo(0, y);
      gridCtx.lineTo(w, y);
    }
    gridCtx.stroke();
  }

  gridCtx.restore();
}

// =========================================================
// Viewport Resizing
// =========================================================
function resizeCanvases() {
  const w = window.innerWidth;
  const h = window.innerHeight;

  let tempCanvas = null;
  if (drawingCanvas.width > 0 && drawingCanvas.height > 0) {
    tempCanvas = document.createElement('canvas');
    tempCanvas.width = drawingCanvas.width;
    tempCanvas.height = drawingCanvas.height;
    tempCanvas.getContext('2d').drawImage(drawingCanvas, 0, 0);
  }

  [cameraCanvas, gridCanvas, drawingCanvas, previewCanvas, particleCanvas].forEach((c) => {
    c.width = w;
    c.height = h;
  });

  pipCanvas.width = 250;
  pipCanvas.height = 140;

  if (tempCanvas) {
    drawCtx.drawImage(tempCanvas, 0, 0);
  }

  renderGrid();
}
window.addEventListener('resize', resizeCanvases);
resizeCanvases();

// =========================================================
// Toast Notification Engine
// =========================================================
let toastTimeout = null;
function showToast(msg, icon = '✨', duration = 2400) {
  toastMessage.textContent = msg;
  toastIcon.textContent = icon;
  toastBanner.classList.add('show');
  if (toastTimeout) clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toastBanner.classList.remove('show');
  }, duration);
}

// =========================================================
// History Stack (Undo & Redo)
// =========================================================
function pushUndoState() {
  if (STATE.undoStack.length >= CONFIG.maxHistoryStates) {
    STATE.undoStack.shift();
  }
  const imgData = drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height);
  STATE.undoStack.push(imgData);
  STATE.redoStack = [];
}

function undo() {
  if (STATE.undoStack.length === 0) {
    showToast('Nothing to undo', '⚠️');
    return;
  }
  const currData = drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height);
  STATE.redoStack.push(currData);
  const prevData = STATE.undoStack.pop();
  drawCtx.putImageData(prevData, 0, 0);
  playSound('click');
  showToast('Undo Stroke', '↩️');
}

function redo() {
  if (STATE.redoStack.length === 0) {
    showToast('Nothing to redo', '⚠️');
    return;
  }
  const currData = drawCtx.getImageData(0, 0, drawingCanvas.width, drawingCanvas.height);
  STATE.undoStack.push(currData);
  const nextData = STATE.redoStack.pop();
  drawCtx.putImageData(nextData, 0, 0);
  playSound('click');
  showToast('Redo Stroke', '↪️');
}

function clearCanvas() {
  pushUndoState();
  drawCtx.clearRect(0, 0, drawingCanvas.width, drawingCanvas.height);
  spawnClearBurst();
  playSound('clear');
  showToast('Canvas Cleared (Undo with Ctrl+Z)', '🧹');
}

// =========================================================
// Drawing Mechanics & Bézier Spline Interpolation
// =========================================================
function drawSmoothStrokeSegment(points, color, size, isHighlighter, isNeon) {
  if (points.length < 2) return;
  drawCtx.save();
  drawCtx.lineCap = 'round';
  drawCtx.lineJoin = 'round';

  if (isHighlighter) {
    drawCtx.globalAlpha = 0.35;
    drawCtx.strokeStyle = color;
    drawCtx.lineWidth = size * 2.5 + 4;
    drawCtx.shadowBlur = 0;
  } else if (isNeon) {
    drawCtx.globalAlpha = 1.0;
    drawCtx.strokeStyle = '#FFFFFF'; // core white light
    drawCtx.lineWidth = size;
    drawCtx.shadowColor = color;
    drawCtx.shadowBlur = Math.max(14, size * 2.4);
  } else {
    drawCtx.globalAlpha = 1.0;
    drawCtx.strokeStyle = color;
    drawCtx.lineWidth = size;
    drawCtx.shadowBlur = 0;
  }

  const p1 = points[points.length - 2];
  const p2 = points[points.length - 1];

  drawCtx.beginPath();
  drawCtx.moveTo(p1.x, p1.y);

  // Midpoint quadratic Bézier smoothing
  const midX = (p1.x + p2.x) / 2;
  const midY = (p1.y + p2.y) / 2;
  drawCtx.quadraticCurveTo(p1.x, p1.y, midX, midY);
  drawCtx.lineTo(p2.x, p2.y);
  drawCtx.stroke();

  // If neon, overlay color wash
  if (isNeon) {
    drawCtx.strokeStyle = color;
    drawCtx.lineWidth = size + 4;
    drawCtx.globalAlpha = 0.55;
    drawCtx.stroke();
  }

  drawCtx.restore();
}

function eraseAt(pt, radius) {
  drawCtx.save();
  drawCtx.globalCompositeOperation = 'destination-out';
  drawCtx.beginPath();
  drawCtx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
  drawCtx.fill();
  drawCtx.restore();

  // Sparkle erasure smoke
  if (Math.random() < 0.4) {
    spawnParticles(pt.x, pt.y, 2, 'rgba(255, 51, 102, 0.7)', 1.5);
  }
}

function renderShape(ctx, start, end, tool, color, size, isPreview = false) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = size;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  if (isPreview) {
    ctx.setLineDash([8, 6]);
    ctx.globalAlpha = 0.85;
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
  }

  const dx = end.x - start.x;
  const dy = end.y - start.y;

  if (tool === 'line') {
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();
  } else if (tool === 'rectangle') {
    ctx.beginPath();
    ctx.strokeRect(start.x, start.y, dx, dy);
  } else if (tool === 'circle') {
    const radius = Math.hypot(dx, dy);
    if (radius > 2) {
      ctx.beginPath();
      ctx.arc(start.x, start.y, radius, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else if (tool === 'arrow') {
    const len = Math.hypot(dx, dy);
    if (len > 5) {
      ctx.beginPath();
      ctx.moveTo(start.x, start.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();

      const headLen = Math.min(32, Math.max(14, size * 3));
      const angle = Math.atan2(dy, dx);
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(end.x, end.y);
      ctx.lineTo(
        end.x - headLen * Math.cos(angle - Math.PI / 6),
        end.y - headLen * Math.sin(angle - Math.PI / 6)
      );
      ctx.moveTo(end.x, end.y);
      ctx.lineTo(
        end.x - headLen * Math.cos(angle + Math.PI / 6),
        end.y - headLen * Math.sin(angle + Math.PI / 6)
      );
      ctx.stroke();
    }
  }

  ctx.restore();
}

function finishStroke() {
  if (STATE.isDrawingShape && STATE.shapeStartPoint && STATE.prevPoint) {
    pushUndoState();
    renderShape(drawCtx, STATE.shapeStartPoint, STATE.prevPoint, STATE.tool, STATE.color, STATE.size, false);
    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    STATE.isDrawingShape = false;
    STATE.shapeStartPoint = null;
    playSound('click');
  }

  STATE.prevPoint = null;
  STATE.currentStrokePoints = [];
  STATE.strokeInProgress = false;
}

// =========================================================
// Living Doodles Animation Engine ("Bring to Life")
// =========================================================
class WebAliveDoodle {
  constructor(canvasSprite, x, y) {
    this.sprite = canvasSprite;
    this.w = canvasSprite.width;
    this.h = canvasSprite.height;
    this.x = x;
    this.y = y;
    const angle = (Math.random() - 0.5) * Math.PI * 0.8 + (Math.random() > 0.5 ? Math.PI : 0);
    const speed = 2.4 + Math.random() * 2.0;
    this.vx = Math.cos(angle) * speed;
    this.vy = Math.sin(angle) * speed * 0.35;
    this.phase = Math.random() * 6.28;
    this.wiggleSpeed = 0.22;
    this.bubbles = [];
  }

  update(boundsW, boundsH, handPt, gesture) {
    this.phase += this.wiggleSpeed;

    if (handPt) {
      const dist = Math.hypot(handPt.x - this.x, handPt.y - this.y);
      if ((gesture === 'SELECT' || gesture === 'PINCH' || gesture === 'DRAW') && dist < 420) {
        const pull = gesture === 'PINCH' ? 0.16 : 0.08;
        const angle = Math.atan2(handPt.y - this.y, handPt.x - this.x);
        this.vx += Math.cos(angle) * pull;
        this.vy += Math.sin(angle) * pull;
      } else if (gesture === 'ERASER' && dist < 280) {
        const angle = Math.atan2(this.y - handPt.y, this.x - handPt.x);
        this.vx += Math.cos(angle) * 0.55;
        this.vy += Math.sin(angle) * 0.55;
      }
    }

    this.vx += (Math.random() - 0.5) * 0.24;
    this.vy += (Math.random() - 0.5) * 0.16;

    const speed = Math.hypot(this.vx, this.vy);
    if (speed > 6.0) {
      this.vx = (this.vx / speed) * 6.0;
      this.vy = (this.vy / speed) * 6.0;
    } else if (speed < 1.4) {
      this.vx = (this.vx / Math.max(0.1, speed)) * 2.0;
      this.vy = (this.vy / Math.max(0.1, speed)) * 0.8;
    }

    this.x += this.vx;
    this.y += this.vy;

    const padX = this.w / 2 + 20;
    const padY = this.h / 2 + 75;
    if (this.x < padX) { this.x = padX; this.vx = Math.abs(this.vx) * 0.95 + 0.8; }
    else if (this.x > boundsW - padX) { this.x = boundsW - padX; this.vx = -Math.abs(this.vx) * 0.95 - 0.8; }

    if (this.y < padY) { this.y = padY; this.vy = Math.abs(this.vy) * 0.95 + 0.5; }
    else if (this.y > boundsH - (this.h / 2 + 20)) { this.y = boundsH - (this.h / 2 + 20); this.vy = -Math.abs(this.vy) * 0.95 - 0.5; }

    if (Math.random() < 0.05) {
      const bx = this.x - Math.sign(this.vx || 1) * (this.w / 2);
      const by = this.y + (Math.random() - 0.5) * 8;
      this.bubbles.push({ x: bx, y: by, r: 3 + Math.random() * 4, alpha: 0.85 });
    }

    for (let i = this.bubbles.length - 1; i >= 0; i--) {
      const b = this.bubbles[i];
      b.y -= 1.6;
      b.alpha -= 0.018;
      if (b.alpha <= 0 || b.y < 70) this.bubbles.splice(i, 1);
    }
  }

  draw(ctx) {
    ctx.save();
    ctx.translate(this.x, this.y);
    if (this.vx < 0) {
      ctx.scale(-1, 1);
    }
    const wobbleAngle = 0.10 * Math.sin(this.phase);
    ctx.rotate(wobbleAngle);
    ctx.drawImage(this.sprite, -this.w / 2, -this.h / 2);
    ctx.restore();

    ctx.save();
    for (const b of this.bubbles) {
      ctx.strokeStyle = `rgba(220, 240, 255, ${b.alpha})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
}

function animateLastDrawing() {
  const w = drawingCanvas.width;
  const h = drawingCanvas.height;
  const imgData = drawCtx.getImageData(0, 0, w, h);
  const data = imgData.data;

  let minX = w, minY = h, maxX = 0, maxY = 0;
  let count = 0;

  for (let y = 75; y < h; y += 2) {
    for (let x = 0; x < w; x += 2) {
      const alpha = data[(y * w + x) * 4 + 3];
      if (alpha > 30) {
        count++;
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }

  if (count < 40 || maxX <= minX || maxY <= minY) {
    showToast('Draw a doodle first to bring it alive!', '✨');
    return;
  }

  const pad = 12;
  const cropX = Math.max(0, minX - pad);
  const cropY = Math.max(0, minY - pad);
  const cropW = Math.min(w - cropX, (maxX - minX) + pad * 2);
  const cropH = Math.min(h - cropY, (maxY - minY) + pad * 2);

  const offscreen = document.createElement('canvas');
  offscreen.width = cropW;
  offscreen.height = cropH;
  const offCtx = offscreen.getContext('2d');
  offCtx.drawImage(drawingCanvas, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);

  pushUndoState();
  drawCtx.clearRect(cropX, cropY, cropW, cropH);

  const doodle = new WebAliveDoodle(offscreen, cropX + cropW / 2, cropY + cropH / 2);
  STATE.aliveDoodles.push(doodle);
  playSound('magic');
  showToast(`Doodle brought to life! (${STATE.aliveDoodles.length} active ✨)`, '🐟');
}


// =========================================================
// Adaptive Landmark Smoothing (EMA)
// =========================================================
function smoothPoint(rawPoint, isDrawing) {
  if (!STATE.smoothIndexTip) {
    STATE.smoothIndexTip = { ...rawPoint };
    return rawPoint;
  }

  const dx = rawPoint.x - STATE.smoothIndexTip.x;
  const dy = rawPoint.y - STATE.smoothIndexTip.y;
  const dist = Math.hypot(dx, dy);

  const baseAlpha = isDrawing ? CONFIG.smoothAlphaDraw : CONFIG.smoothAlphaHover;
  const speedBoost = Math.min(0.45, dist / 110.0);
  const alpha = Math.min(0.95, baseAlpha + speedBoost);

  const sx = alpha * rawPoint.x + (1.0 - alpha) * STATE.smoothIndexTip.x;
  const sy = alpha * rawPoint.y + (1.0 - alpha) * STATE.smoothIndexTip.y;

  STATE.smoothIndexTip = { x: sx, y: sy };
  return STATE.smoothIndexTip;
}

// =========================================================
// Gesture Recognition Engine & Telemetry
// =========================================================
function classifyGestures(landmarks) {
  // landmarks: 21 points
  const fingers = [false, false, false, false, false];

  // 1. Thumb extension test
  const thumbTip = landmarks[4];
  const pinkyMcp = landmarks[17];
  const thumbIp = landmarks[3];
  const wrist = landmarks[0];

  const distThumbPinky = Math.hypot(thumbTip.x - pinkyMcp.x, thumbTip.y - pinkyMcp.y);
  const distIpPinky = Math.hypot(thumbIp.x - pinkyMcp.x, thumbIp.y - pinkyMcp.y);
  if (distThumbPinky > distIpPinky * 1.15) {
    fingers[0] = true;
  }

  // 2. Index
  if (landmarks[8].y < landmarks[6].y && landmarks[8].y < landmarks[7].y) fingers[1] = true;
  // 3. Middle
  if (landmarks[12].y < landmarks[10].y && landmarks[12].y < landmarks[11].y) fingers[2] = true;
  // 4. Ring
  if (landmarks[16].y < landmarks[14].y && landmarks[16].y < landmarks[15].y) fingers[3] = true;
  // 5. Pinky
  if (landmarks[20].y < landmarks[18].y && landmarks[20].y < landmarks[19].y) fingers[4] = true;

  STATE.fingersUp = fingers;
  updateBiometricHUD(fingers);

  const [thumb, index, middle, ring, pinky] = fingers;
  const numExtended = fingers.filter(Boolean).length;

  // Pinch distance between index tip (8) and thumb tip (4)
  const pinchDist = Math.hypot(landmarks[8].x - landmarks[4].x, landmarks[8].y - landmarks[4].y);
  const isPinch = pinchDist < CONFIG.pinchThresholdNorm;

  if (isPinch) return 'PINCH';
  if (numExtended >= 4 || (index && middle && ring && !pinky)) return 'ERASER';
  if (index && middle && !ring && !pinky) return 'SELECT';
  if (index && !middle && !ring && !pinky) return 'DRAW';
  if (numExtended === 0) return 'FIST';

  return 'NONE';
}

function updateBiometricHUD(fingers) {
  fingerNodes.thumb.classList.toggle('active', fingers[0]);
  fingerNodes.index.classList.toggle('active', fingers[1]);
  fingerNodes.middle.classList.toggle('active', fingers[2]);
  fingerNodes.ring.classList.toggle('active', fingers[3]);
  fingerNodes.pinky.classList.toggle('active', fingers[4]);
}

// =========================================================
// UI Dwell & Pinch Hit-Testing Engine
// =========================================================
function checkToolbarHover(cursorPt, isPinching) {
  if (!cursorPt) {
    resetDwell();
    return null;
  }

  const el = document.elementFromPoint(cursorPt.x, cursorPt.y);
  const targetBtn = el ? el.closest('.tool-btn, .color-swatch, .size-btn, .action-btn, .color-picker-label') : null;

  if (!targetBtn) {
    resetDwell();
    return null;
  }

  const now = performance.now();
  if (STATE.hoveredElement !== targetBtn) {
    STATE.hoveredElement = targetBtn;
    STATE.hoverStartTime = now;
    STATE.dwellProgress = 0;
    if (isPinching) {
      triggerButtonAction(targetBtn);
    }
    return targetBtn;
  }

  const elapsed = now - STATE.hoverStartTime;
  STATE.dwellProgress = Math.min(1.0, elapsed / CONFIG.dwellTimeMs);

  const circumference = 2 * Math.PI * 20; // ~125.6
  const offset = circumference * (1.0 - STATE.dwellProgress);
  dwellFillCircle.style.strokeDashoffset = offset;

  if (STATE.dwellProgress >= 1.0 || isPinching) {
    triggerButtonAction(targetBtn);
    resetDwell();
  }

  return targetBtn;
}

function resetDwell() {
  STATE.hoveredElement = null;
  STATE.hoverStartTime = null;
  STATE.dwellProgress = 0;
  dwellFillCircle.style.strokeDashoffset = '125.6';
}

function triggerButtonAction(btn) {
  playSound('pinch');
  spawnParticles(cursorDot.getBoundingClientRect().left, cursorDot.getBoundingClientRect().top, 6, STATE.color);
  btn.click();
}

// =========================================================
// Interactive Controls & Toolbar Handlers
// =========================================================
// Tool Switching
document.querySelectorAll('.tool-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tool-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.tool = btn.dataset.tool;
    finishStroke();
    playSound('click');
    showToast(`Tool: ${btn.dataset.tool.toUpperCase()}`, '🎨');
    updateHud();
    updateCapsule();
  });
});

// Color Selection
document.querySelectorAll('.color-swatch').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.color-swatch').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    setColor(btn.dataset.color, btn.dataset.tooltip || 'Color');
  });
});

// HTML5 Custom Color Picker
customColorInput.addEventListener('input', (e) => {
  setColor(e.target.value, 'Custom Color');
});

function setColor(hex, label = 'Color') {
  STATE.color = hex;
  cursorDot.style.background = STATE.color;
  cursorDot.style.boxShadow = `0 0 14px ${STATE.color}`;
  cursorGlow.style.background = `radial-gradient(circle, ${STATE.color}77 0%, transparent 70%)`;
  sizePreviewDot.style.background = STATE.color;
  capsuleColorDot.style.background = STATE.color;
  playSound('click');
  showToast(`Color: ${label}`, '🎨');
  updateHud();
}

// Brush Size Selection
document.querySelectorAll('.size-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.size-btn').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.size = parseInt(btn.dataset.size, 10);
    sizePreviewDot.style.width = `${Math.min(20, Math.max(4, STATE.size))}px`;
    sizePreviewDot.style.height = `${Math.min(20, Math.max(4, STATE.size))}px`;
    playSound('click');
    showToast(`Brush Size: ${STATE.size}px`, '🖌️');
    updateHud();
  });
});

// History & Clear
document.getElementById('btnUndo').addEventListener('click', undo);
document.getElementById('btnRedo').addEventListener('click', redo);
document.getElementById('btnClear').addEventListener('click', clearCanvas);

// Background Mode Switcher
document.getElementById('btnThemeMode').addEventListener('click', () => {
  const modes = ['camera', 'whiteboard', 'blackboard', 'blueprint'];
  const labels = {
    camera: 'AR Cam',
    whiteboard: 'Whiteboard',
    blackboard: 'Blackboard',
    blueprint: 'Blueprint',
  };
  const nextIdx = (modes.indexOf(STATE.canvasMode) + 1) % modes.length;
  STATE.canvasMode = modes[nextIdx];

  document.body.className = `mode-${STATE.canvasMode}`;
  themeModeLabel.textContent = labels[STATE.canvasMode];
  pipContainer.style.display = STATE.canvasMode === 'camera' ? 'none' : 'block';
  renderGrid();
  playSound('mode');
  showToast(`Theme: ${labels[STATE.canvasMode]}`, '🌌');
});

// Grid Toggle
document.getElementById('btnToggleGrid').addEventListener('click', () => {
  const gridCycle = ['none', 'dots', 'graph', 'blueprint'];
  const nextIdx = (gridCycle.indexOf(STATE.gridMode) + 1) % gridCycle.length;
  STATE.gridMode = gridCycle[nextIdx];
  renderGrid();
  playSound('click');
  showToast(`Grid: ${STATE.gridMode.toUpperCase()}`, '📐');
});

// Sound Toggle
document.getElementById('btnToggleAudio').addEventListener('click', () => {
  STATE.soundEnabled = !STATE.soundEnabled;
  updateAudioUI();
  if (STATE.soundEnabled) playSound('click');
  showToast(STATE.soundEnabled ? 'Audio FX Enabled' : 'Audio FX Muted', STATE.soundEnabled ? '🔔' : '🔕');
});
updateAudioUI();

// Alive Doodle Action Hook
const btnAlive = document.getElementById('btnAlive');
if (btnAlive) {
  btnAlive.addEventListener('click', animateLastDrawing);
}

// Fullscreen
document.getElementById('btnFullscreen').addEventListener('click', () => {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
    showToast('Fullscreen Mode', '⛶');
  } else {
    document.exitFullscreen().catch(() => {});
    showToast('Exited Fullscreen', '⛶');
  }
});

// Toolbar Minimizer / Collapser
document.getElementById('btnCollapseToolbar').addEventListener('click', () => {
  toolbarWrapper.classList.add('collapsed');
  playSound('click');
  showToast('Dock Minimized (Click Capsule to Restore)', '📦');
});
document.getElementById('btnExpandToolbar').addEventListener('click', () => {
  toolbarWrapper.classList.remove('collapsed');
  playSound('click');
});
collapsedCapsule.addEventListener('click', () => {
  toolbarWrapper.classList.remove('collapsed');
  playSound('click');
});

function updateCapsule() {
  capsuleToolLabel.textContent = STATE.tool;
}

// Exports
document.getElementById('btnExportPng').addEventListener('click', () => exportImage('png'));
document.getElementById('btnExportPdf').addEventListener('click', () => exportPdf());
document.getElementById('btnCopyClipboard').addEventListener('click', copyCanvasToClipboard);

// Guide Modal Handlers
btnOpenGuide.addEventListener('click', () => {
  guideModalBackdrop.classList.add('open');
  playSound('click');
});
btnCloseGuide.addEventListener('click', () => {
  guideModalBackdrop.classList.remove('open');
});
btnDismissGuide.addEventListener('click', () => {
  guideModalBackdrop.classList.remove('open');
});
guideModalBackdrop.addEventListener('click', (e) => {
  if (e.target === guideModalBackdrop) {
    guideModalBackdrop.classList.remove('open');
  }
});

// PiP Toggle
document.getElementById('btnPipToggle').addEventListener('click', () => {
  const body = document.getElementById('pipBody');
  body.style.display = body.style.display === 'none' ? 'block' : 'none';
  playSound('click');
});

function updateHud() {
  hudTool.textContent = `${STATE.tool.toUpperCase()} (${STATE.size}px)`;
  hudGestureMode.textContent = STATE.currentGesture;

  const gestureColors = {
    DRAW: '#10B981',
    SELECT: '#00F0FF',
    PINCH: '#A855F7',
    ERASER: '#FF3366',
    FIST: '#64748B',
    NONE: '#475569',
  };
  const color = gestureColors[STATE.currentGesture] || '#00F0FF';
  gestureBadgeDot.style.background = color;
  gestureBadgeDot.style.boxShadow = `0 0 8px ${color}`;

  // Highlight pill in bottom gesture helper
  document.querySelectorAll('.helper-pill').forEach((pill) => {
    pill.classList.toggle('highlight', pill.dataset.gesture === STATE.currentGesture);
  });
}

// =========================================================
// Image, PDF & Clipboard Export Suite
// =========================================================
function getExportCanvas() {
  const exportCanvas = document.createElement('canvas');
  exportCanvas.width = drawingCanvas.width;
  exportCanvas.height = drawingCanvas.height;
  const ctx = exportCanvas.getContext('2d');

  if (STATE.canvasMode === 'whiteboard') {
    ctx.fillStyle = '#FFFFFF';
  } else if (STATE.canvasMode === 'blackboard') {
    ctx.fillStyle = '#0B101E';
  } else if (STATE.canvasMode === 'blueprint') {
    ctx.fillStyle = '#041026';
  } else {
    // In AR camera mode, default to sleek dark background
    ctx.fillStyle = '#030712';
  }
  ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);

  // Draw grid if active
  if (STATE.gridMode !== 'none') {
    ctx.drawImage(gridCanvas, 0, 0);
  }

  // Draw digital ink
  ctx.drawImage(drawingCanvas, 0, 0);
  return exportCanvas;
}

function exportImage(format = 'png') {
  const exportCanvas = getExportCanvas();
  const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
  const filename = `AirScribe_Note_${timestamp}.${format}`;
  const link = document.createElement('a');
  link.download = filename;
  link.href = exportCanvas.toDataURL(`image/${format}`, 0.95);
  link.click();
  playSound('success');
  showToast(`Downloaded ${filename}`, '📥');
}

function exportPdf() {
  if (!window.jspdf) {
    showToast('PDF generator loading...', '⏳');
    return;
  }
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({
    orientation: drawingCanvas.width > drawingCanvas.height ? 'landscape' : 'portrait',
    unit: 'px',
    format: [drawingCanvas.width, drawingCanvas.height],
  });

  const exportCanvas = getExportCanvas();
  const imgData = exportCanvas.toDataURL('image/jpeg', 0.95);
  pdf.addImage(imgData, 'JPEG', 0, 0, drawingCanvas.width, drawingCanvas.height);

  const timestamp = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
  const filename = `AirScribe_Note_${timestamp}.pdf`;
  pdf.save(filename);
  playSound('success');
  showToast(`Exported ${filename}`, '📄');
}

async function copyCanvasToClipboard() {
  const exportCanvas = getExportCanvas();
  try {
    exportCanvas.toBlob(async (blob) => {
      if (!blob) throw new Error('Blob creation failed');
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);
      playSound('success');
      showToast('Copied Note to Clipboard!', '📋');
    });
  } catch (err) {
    showToast('Clipboard copy not supported by browser', '⚠️');
  }
}

// =========================================================
// Skeleton Drawing on PiP Viewport
// =========================================================
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

function drawSkeleton(ctx, landmarks, w, h) {
  ctx.strokeStyle = 'rgba(0, 240, 255, 0.85)';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';

  HAND_CONNECTIONS.forEach(([i, j]) => {
    ctx.beginPath();
    ctx.moveTo((1.0 - landmarks[i].x) * w, landmarks[i].y * h);
    ctx.lineTo((1.0 - landmarks[j].x) * w, landmarks[j].y * h);
    ctx.stroke();
  });

  landmarks.forEach((lm, idx) => {
    ctx.fillStyle = idx === 8 ? '#FF007A' : (idx === 4 ? '#FFB800' : '#FFFFFF');
    ctx.beginPath();
    ctx.arc((1.0 - lm.x) * w, lm.y * h, idx === 8 ? 4.5 : 2.5, 0, Math.PI * 2);
    ctx.fill();
  });
}

// =========================================================
// Animation Loop (Particles & Laser Wand)
// =========================================================
function mainVfxLoop() {
  updateAndRenderParticles();
  updateAndRenderWandTrails();
  updateAndRenderAliveDoodles();
  requestAnimationFrame(mainVfxLoop);
}
requestAnimationFrame(mainVfxLoop);

function updateAndRenderAliveDoodles() {
  if (STATE.aliveDoodles.length === 0) return;
  const w = drawingCanvas.width;
  const h = drawingCanvas.height;

  if (!STATE.isDrawingShape && wandTrails.length === 0) {
    previewCtx.clearRect(0, 0, w, h);
  }

  STATE.aliveDoodles.forEach((doodle) => {
    doodle.update(w, h, STATE.smoothIndexTip, STATE.currentGesture);
    doodle.draw(previewCtx);
  });
}

// =========================================================
// Frame Processing & MediaPipe Results
// =========================================================
function onHandResults(results) {
  const now = performance.now();
  STATE.fps = Math.round(1000 / Math.max(1, now - STATE.lastFrameTime));
  STATE.lastFrameTime = now;
  hudFps.textContent = `${STATE.fps} FPS`;

  const w = window.innerWidth;
  const h = window.innerHeight;

  // 1. AR Camera Video Layer
  if (STATE.canvasMode === 'camera') {
    cameraCtx.save();
    cameraCtx.clearRect(0, 0, w, h);
    cameraCtx.translate(w, 0);
    cameraCtx.scale(-1, 1);
    cameraCtx.drawImage(results.image, 0, 0, w, h);
    cameraCtx.restore();
  } else {
    cameraCtx.clearRect(0, 0, w, h);
  }

  // 2. Picture-in-Picture Mini Viewport
  pipCtx.save();
  pipCtx.clearRect(0, 0, pipCanvas.width, pipCanvas.height);
  pipCtx.translate(pipCanvas.width, 0);
  pipCtx.scale(-1, 1);
  pipCtx.drawImage(results.image, 0, 0, pipCanvas.width, pipCanvas.height);
  pipCtx.restore();

  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0) {
    virtualCursor.classList.remove('visible');
    finishStroke();
    STATE.currentGesture = 'NONE';
    updateBiometricHUD([false, false, false, false, false]);
    updateHud();
    return;
  }

  // Extract Primary Hand
  const lms = results.multiHandLandmarks[0];
  drawSkeleton(pipCtx, lms, pipCanvas.width, pipCanvas.height);

  const rawX = (1.0 - lms[8].x) * w;
  const rawY = lms[8].y * h;
  const rawTip = { x: rawX, y: rawY };

  // Classify Gesture
  const gesture = classifyGestures(lms);
  STATE.currentGesture = gesture;
  updateHud();

  const isDrawing = (gesture === 'DRAW');
  const smoothed = smoothPoint(rawTip, isDrawing);

  // Position Virtual Reticle
  virtualCursor.style.left = `${smoothed.x}px`;
  virtualCursor.style.top = `${smoothed.y}px`;
  virtualCursor.classList.add('visible');

  // Reticle Eraser Ring
  virtualCursor.classList.toggle('eraser-mode', gesture === 'ERASER' || STATE.tool === 'eraser');

  const badgeMap = {
    DRAW: '✍️',
    SELECT: '✌️',
    ERASER: '🧹',
    PINCH: '🤏',
    FIST: '✊',
    NONE: '✋',
  };
  cursorBadge.textContent = badgeMap[gesture] || '✋';

  // 3. Test Toolbar Interaction
  const hovered = checkToolbarHover(smoothed, gesture === 'PINCH');
  const inToolbarArea = smoothed.y < 95;

  if (inToolbarArea || hovered) {
    finishStroke();
    return;
  }

  // 4. Drawing & Eraser Mechanics
  if (gesture === 'ERASER' || STATE.tool === 'eraser') {
    if (!STATE.strokeInProgress) {
      pushUndoState();
      STATE.strokeInProgress = true;
    }
    const r = gesture === 'ERASER' ? STATE.eraserRadius * 2 : STATE.eraserRadius;
    eraseAt(smoothed, r);
    STATE.prevPoint = smoothed;
    return;
  }

  if (gesture === 'DRAW') {
    // Continuous Freehand Ink / Neon / Highlighter / Laser Wand
    if (['pen', 'neon', 'wand', 'highlighter'].includes(STATE.tool)) {
      if (!STATE.strokeInProgress) {
        pushUndoState();
        STATE.strokeInProgress = true;
        STATE.currentStrokePoints = [smoothed];
      }

      if (!STATE.prevPoint) STATE.prevPoint = smoothed;

      STATE.currentStrokePoints.push(smoothed);

      if (STATE.tool === 'wand') {
        // Laser wand records fading trail segment
        wandTrails.push({
          points: [STATE.prevPoint, smoothed],
          color: STATE.color,
          size: STATE.size * 1.5,
          bornAt: performance.now(),
        });
        spawnParticles(smoothed.x, smoothed.y, 1, STATE.color, 1.2);
      } else {
        drawSmoothStrokeSegment(
          STATE.currentStrokePoints,
          STATE.color,
          STATE.size,
          STATE.tool === 'highlighter',
          STATE.tool === 'neon'
        );
        // Subtle cyber sparkle trail
        if (STATE.tool === 'neon') {
          spawnParticles(smoothed.x, smoothed.y, 2, STATE.color, 2);
        } else if (Math.random() < 0.25) {
          spawnParticles(smoothed.x, smoothed.y, 1, STATE.color, 1);
        }
      }

      STATE.prevPoint = smoothed;
    }
    // Shape Drag Previews
    else if (['line', 'rectangle', 'circle', 'arrow'].includes(STATE.tool)) {
      if (!STATE.isDrawingShape) {
        STATE.shapeStartPoint = smoothed;
        STATE.isDrawingShape = true;
      }
      STATE.prevPoint = smoothed;
      previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
      renderShape(previewCtx, STATE.shapeStartPoint, smoothed, STATE.tool, STATE.color, STATE.size, true);
    }
  } else {
    finishStroke();
  }
}

// =========================================================
// Keyboard Hotkeys Engine
// =========================================================
window.addEventListener('keydown', (e) => {
  // If dialog is open and Escape pressed, close it
  if (e.key === 'Escape' && guideModalBackdrop.classList.contains('open')) {
    guideModalBackdrop.classList.remove('open');
    return;
  }

  if (e.ctrlKey && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    undo();
  } else if (e.ctrlKey && e.key.toLowerCase() === 'y') {
    e.preventDefault();
    redo();
  } else if (e.key.toLowerCase() === 'c') {
    clearCanvas();
  } else if (e.key.toLowerCase() === 's') {
    exportImage('png');
  } else if (e.key.toLowerCase() === 'p') {
    exportPdf();
  } else if (e.key.toLowerCase() === 'm') {
    document.getElementById('btnThemeMode').click();
  } else if (e.key.toLowerCase() === 'g') {
    document.getElementById('btnToggleGrid').click();
  } else if (e.key.toLowerCase() === 'u') {
    document.getElementById('btnToggleAudio').click();
  } else if (e.key.toLowerCase() === 'f') {
    document.getElementById('btnFullscreen').click();
  } else if (e.key === '?') {
    btnOpenGuide.click();
  } else if (e.key.toLowerCase() === 'd') {
    document.getElementById('btnToolPen').click();
  } else if (e.key.toLowerCase() === 'w') {
    animateLastDrawing();
  } else if (e.key.toLowerCase() === 'k') {
    const btnLaser = document.getElementById('btnToolLaser');
    if (btnLaser) btnLaser.click();
  } else if (e.key.toLowerCase() === 'j') {
    const btnSpot = document.getElementById('btnToolSpotlight');
    if (btnSpot) btnSpot.click();
  } else if (e.key.toLowerCase() === 'h') {
    document.getElementById('btnToolHighlighter').click();
  } else if (e.key.toLowerCase() === 'e') {
    document.getElementById('btnToolEraser').click();
  } else if (e.key.toLowerCase() === 'l') {
    document.getElementById('btnToolLine').click();
  } else if (e.key.toLowerCase() === 'r') {
    document.getElementById('btnToolRect').click();
  } else if (e.key.toLowerCase() === 'o') {
    document.getElementById('btnToolCircle').click();
  } else if (e.key.toLowerCase() === 'a') {
    document.getElementById('btnToolArrow').click();
  } else if (['1', '2', '3', '4'].includes(e.key)) {
    const sizeBtns = document.querySelectorAll('.size-btn');
    const idx = parseInt(e.key, 10) - 1;
    if (sizeBtns[idx]) sizeBtns[idx].click();
  }
});

// =========================================================
// Mouse & Touch Fallback Support
// =========================================================
let isMouseDown = false;
window.addEventListener('mousedown', (e) => {
  if (e.clientY < 95 || e.target.closest('.toolbar-wrapper, .status-hud, .pip-container, .guide-modal')) return;
  isMouseDown = true;
  initAudio();
  pushUndoState();
  const pt = { x: e.clientX, y: e.clientY };
  STATE.prevPoint = pt;
  STATE.currentStrokePoints = [pt];

  if (['line', 'rectangle', 'circle', 'arrow'].includes(STATE.tool)) {
    STATE.shapeStartPoint = pt;
    STATE.isDrawingShape = true;
  }
});

window.addEventListener('mousemove', (e) => {
  if (!isMouseDown) return;
  const curr = { x: e.clientX, y: e.clientY };

  if (STATE.tool === 'eraser') {
    eraseAt(curr, STATE.eraserRadius);
  } else if (['pen', 'neon', 'wand', 'highlighter'].includes(STATE.tool)) {
    STATE.currentStrokePoints.push(curr);
    if (STATE.tool === 'wand') {
      wandTrails.push({
        points: [STATE.prevPoint, curr],
        color: STATE.color,
        size: STATE.size * 1.5,
        bornAt: performance.now(),
      });
      spawnParticles(curr.x, curr.y, 1, STATE.color, 1.2);
    } else {
      drawSmoothStrokeSegment(
        STATE.currentStrokePoints,
        STATE.color,
        STATE.size,
        STATE.tool === 'highlighter',
        STATE.tool === 'neon'
      );
      if (STATE.tool === 'neon') spawnParticles(curr.x, curr.y, 1, STATE.color, 2);
    }
    STATE.prevPoint = curr;
  } else if (STATE.isDrawingShape) {
    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    renderShape(previewCtx, STATE.shapeStartPoint, curr, STATE.tool, STATE.color, STATE.size, true);
    STATE.prevPoint = curr;
  }
});

window.addEventListener('mouseup', () => {
  if (isMouseDown) {
    isMouseDown = false;
    finishStroke();
  }
});

// =========================================================
// Initialization & Camera Setup
// =========================================================
async function initCameraAndTracker() {
  showToast('Starting Camera & Gesture AI Engine...', '🚀', 3000);

  const hands = new Hands({
    locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
  });

  hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 1,
    minDetectionConfidence: 0.65,
    minTrackingConfidence: 0.65,
  });

  hands.onResults(onHandResults);

  try {
    const camera = new Camera(videoElement, {
      onFrame: async () => {
        await hands.send({ image: videoElement });
      },
      width: 1280,
      height: 720,
    });
    await camera.start();
    STATE.cameraActive = true;
    showToast('Ready! Lift 1 finger to Draw, 2 to Hover', '✨', 3500);
  } catch (err) {
    console.error('Camera access failed:', err);
    showToast('Webcam not active. Mouse/Trackpad drawing is fully active!', '🖱️', 5000);
  }
}

// Start Application on Load
window.addEventListener('DOMContentLoaded', () => {
  initCameraAndTracker();
});
