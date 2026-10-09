# Virtual Whiteboard Using Hand Gestures

A real-time, touchless digital drawing and note-taking application powered by **Computer Vision**, **MediaPipe Hands**, and **OpenCV**. It transforms any standard webcam into an interactive, gesture-controlled smart canvas without requiring touchscreens, styluses, or specialized hardware.

---

## 🌟 Key Features

- **Touchless Hand Tracking & Ergonomics**:
  - 21 3D hand landmarks tracked in real time using Google MediaPipe Tasks API.
  - **Apple Vision Pro Pinch-to-Draw**: Relax your hand and simply pinch thumb and index finger together to draw, eliminating "gorilla arm" fatigue.
  - **3D Z-Depth Contact**: Pushing hand forward towards the camera touches a virtual glass plane, lifting hand hovers without leaving phantom tails.
- **✨ "Bring to Life" Living Doodles**:
  - Draw any doodle (a fish, bird, butterfly, star, or creature) and activate **Alive Mode** (`W` or ✨ button).
  - The drawing lifts off the page into an autonomous, swimming/floating animated creature with sine-wave body undulation, autonomous swimming kinematics, and floating bubble trails!
  - **Interactive Hand Reactivity**: The creature is attracted to your finger when pointing or pinching (like feeding a pet fish!), and darts away when startled with an open palm!
- **Presenter Suite**:
  - **Laser Pointer** (`K`): Dynamic, glowing ruby laser trail that evaporates after 1.3 seconds, perfect for presentations and lectures without cluttering the board.
  - **Spotlight Mode** (`J`): Dims the screen by 75% with a smooth feathered circular aperture following your finger.
- **Designer Curated Color Palette**:
  - Replaced gaudy neon AI colors with an aesthetic, organic designer palette: Royal Indigo, Obsidian Black, Sage Forest, Warm Terracotta, Tuscan Gold, Nordic Slate, Berry Plum, and Chalk White.
- **Rich Drawing Suite**:
  - Tools: Freehand Pen, Translucent Highlighter, Eraser, Geometric Shapes (Line, Rectangle, Circle, Arrow), Laser Pointer, Spotlight.
  - Live Shape Ghost Previews: Real-time visual feedback while dragging shapes.
  - Brush Sizes: Fine (4px), Medium (8px), Bold (15px), Marker (26px).
- **Multi-Level Undo & Redo**: Full 25-step snapshot history stack; easily revert or replay any stroke.
- **Multiple Canvas Modes**:
  - **AR Camera Overlay**: Augmented reality mode drawing directly on top of your mirrored webcam video feed.
  - **Pure Whiteboard**: Crisp digital whiteboard with Picture-in-Picture (PiP) mini-camera in the corner.
  - **Dark Blackboard**: Slate chalkboard theme ideal for presentations and glowing sketches.
- **One-Click Export**: High-resolution **PNG**, **JPG**, and multi-format **PDF** note export.
- **Auditory & Visual Feedback**: Audio clicks, magic chimes, and snap pops via Windows `winsound` / Web Audio API.

---

## 🖐️ Gesture Control Reference

| Gesture | Hand Posture | Action |
|---|---|---|
| **Draw / Write** | Index finger UP (or Pinch-to-draw mode) | Freehand writing or drawing geometric shapes |
| **Select / Hover** | Index & Middle fingers UP (✌️ Peace sign) | Move pointer across screen, hover over buttons to activate |
| **Pinch Click** | Touch Thumb tip and Index tip together (🤏) | Instantly clicks any hovered toolbar button |
| **Quick Eraser** | Open palm (🖐️) or 3+ fingers extended | Activates large circular eraser to wipe strokes |
| **Fish Interaction** | Point / Pinch near Living Doodle | Attracts doodle to swim toward your finger (feed fish) |
| **Fish Scatter** | Open palm near Living Doodle | Frightens doodle, causing it to dart away with bubbles |
| **Clear Canvas** | Hover over 'Clear' button or press `C` | Clears canvas and active living doodles |

---

## ⌨️ Keyboard Shortcuts Reference

| Key | Function |
|---|---|
| `W` | **Bring Doodle Alive!** (Transforms last drawing into swimming/living doodle) |
| `F` | **Freeze Living Doodles** (Bakes swimming creatures back into static ink) |
| `K` | Select **Laser Pointer** tool |
| `J` | Select **Spotlight** presenter mode |
| `T` | Toggle **Apple Vision Pro Pinch-to-Draw** mode |
| `Q` or `ESC` | Quit application |
| `Z` | Undo last stroke |
| `Y` | Redo stroke |
| `C` | Clear canvas and living doodles |
| `S` | Save current notes as PNG image |
| `P` | Export current notes as PDF document |
| `M` | Cycle background mode (*AR Camera* ➔ *Whiteboard* ➔ *Blackboard*) |
| `D` | Select Freehand Pen tool |
| `H` | Select Highlighter tool |
| `E` | Select Eraser tool |
| `L` / `R` / `O` / `A` | Select Line / Rectangle / Circle / Arrow tool |
| `1` - `4` | Brush thickness (*Fine*, *Medium*, *Bold*, *Marker*) |

---

## 📁 Project Architecture

```
new/
├── config.py             # System configuration, color palette, dimensions, thresholds
├── hand_tracker.py       # MediaPipe HandLandmarker wrapper, gesture classifier, EMA smoother
├── canvas_engine.py      # Layered drawing engine, tools, shapes, undo/redo stack
├── ui_overlay.py         # Glassmorphic HUD, interactive buttons, dwell timer, PiP feed
├── exporter.py           # PNG/JPG image and PDF document exporter
├── main.py               # Main application loop and camera coordinator
├── test_system.py        # Automated test suite
├── requirements.txt      # Dependencies list
├── run.bat               # Windows batch launcher
├── run.ps1               # PowerShell launcher
├── models/               # Cached MediaPipe model weights (hand_landmarker.task)
└── saved_notes/          # Target folder for exported PNG and PDF notes
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.8 or higher installed on Windows, macOS, or Linux.
- A functional standard webcam.

### 2. Installation
Install the necessary dependencies:
```bash
pip install -r requirements.txt
```

### 3. Launching the Application
Run via Python:
```bash
python main.py
```
Or simply double-click `run.bat` on Windows!

### 4. Running the Automated Tests
Verify all sub-systems and integrations:
```bash
python test_system.py
```

---

## 🌐 Web App Deployment (Zero Backend, 100% Client-Side)

AirScribe is also built as a modern, high-performance **Web Application** inside `web/` that runs directly in any modern web browser (Chrome, Edge, Firefox, Safari).

### Why Deploy the Web Version?
- **Zero Server Costs**: Computer vision inference runs 100% client-side using WebAssembly and WebGL through `@mediapipe/hands`.
- **Zero Install**: Anyone with a link and a webcam can start drawing immediately without installing Python or dependencies.
- **Cross-Platform**: Works smoothly on Windows, Mac, Linux, Chromebooks, and tablets.

### Local Web Testing:
```bash
python serve_web.py
```
*(Or double-click `run_web.bat` — opens `http://localhost:8000/` automatically!)*

### 1-Click Deployment Options:

#### Option 1: Vercel (Recommended)
1. Push this repository to **GitHub**.
2. Go to [vercel.com](https://vercel.com) and import the repository.
3. Vercel automatically detects the root `vercel.json` configuration.
4. Click **Deploy** — your live link is generated in 30 seconds!

#### Option 2: Netlify
1. Push this repository to **GitHub**.
2. Go to [netlify.com](https://netlify.com) and click **Add new site** > **Import an existing project**.
3. It detects `netlify.toml` with `publish = "web"`.
4. Click **Deploy**.

#### Option 3: GitHub Pages (Free forever)
1. Push to GitHub.
2. In your GitHub repository, go to **Settings** > **Pages**.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Set branch to `main` and folder to `/web` (or root if files are copied).
5. Click **Save**.

---

## ⚙️ Technical Details

- **Hand Landmark Detection**: Uses MediaPipe Hand Landmarker model running on CPU with TensorFlow Lite XNNPACK acceleration.
- **Smoothing Algorithm**: Dynamic exponential moving average adjusting smoothing coefficient based on instantaneous fingertip velocity:
  $$\alpha = \min(0.95, \alpha_{\text{base}} + \frac{\Delta d}{120})$$
- **Canvas Rendering**: 4-channel BGRA matrix with OpenCV anti-aliasing (`cv2.LINE_AA`) for smooth stroke curves.
- **Export Engine**: Pillow RGB to PDF raster converter and OpenCV PNG compression pipeline.
