# BATradar

BATradar is a real-time drone detection and localization system that combines machine learning-based audio classification with acoustic localization techniques. The system continuously monitors audio input from a microphone array, detects drone presence using a trained neural network, and automatically tries to localize detected drones using Time Difference of Arrival (TDOA) and Direction of Arrival (DOA) methods.

## System Overview

BATradar operates in two main modes:

1. **Monitoring Mode**: Continuously analyzes audio streams using an RNN-based classification model to detect drone sounds. When a drone is detected above a configurable threshold, the system automatically triggers localization.

2. **Localization Mode**: Records synchronized audio from a 4-microphone array, computes TDOA measurements, and calculates the drone's position using multilateration and DOA algorithms. The system performs multiple localization cycles to improve accuracy.

The system includes a web-based frontend interface that displays real-time detection results and localization data on an interactive map, along with a REST API and WebSocket server for real-time communication.

## Architecture

### Components

- **Classification Module** (`classification/`): Machine learning models for drone audio detection
- **Localization Module** (`localization/`): TDOA, DOA, and multilateration algorithms
- **Recording Module** (`recording/`): Multi-device audio recording and microphone management
- **System Manager** (`system_manager.py`): Orchestrates detection and localization workflows
- **API Server** (`api_server.py`): FastAPI server with WebSocket support for real-time updates
- **Frontend** (`frontend/`): React/TypeScript web interface with map visualization

### Localization Method

The localization system uses onset-based TDOA calculation, which detects sharp sound onsets in the audio signal. **This method is optimized for sharp impulse sounds and not specifically designed for continuous drone audio signals.** 

Unfortunately, we did not achieve the result to reliably localize drones with our localization experiments, as our hardware setup did not allow better approaches

For drone-specific localization experiments and alternative localization engines we tried to optimize for continuous signals, see the [TDOA-DOA repository](https://github.com/BP-BATradar/TDOA-DOA), where we conducted extensive localization experiments with different versions and engines specifically designed for drone audio characteristics. However, none achieve reliable results.

## Installation

### Prerequisites

- Python 3.8+
- Node.js 16+ (for frontend)
- 4 microphones configured and accessible

### Backend Setup

```bash
cd BATradar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For macOS with TensorFlow issues:

```bash
pip install tensorflow-macos tensorflow-metal  # GPU optional
brew install libsndfile portaudio
```

### Frontend Setup

```bash
cd frontend
npm install
npm run build
```

## Usage

### Starting the System

1. **Start the API server:**

```bash
python api_server.py
```

The server will start on `http://localhost:8000` by default.

2. **Configure microphone devices:**

The system will automatically detect and configure microphones on startup. Ensure 4 microphones are connected and accessible.

3. **Access the frontend:**

Open frontend through npm run dev

### Configuration

**Raspberry Pi Connection:**

The frontend is hardcoded to connect to a specific Raspberry Pi IP address. To change this, edit `frontend/src/components/MapView.tsx` and update the following constants:

```typescript
const API_HOST = '172.20.10.12';  // Change to your Raspberry Pi IP address
const API_PORT = '8000';          // Change if using a different port
```

After making changes, rebuild the frontend:

```bash
cd frontend
npm run build
```

**System Parameters:**

Key parameters can be adjusted in `system_manager.py` initialization:

- `detection_threshold`: Probability threshold for triggering localization (default: 0.5)
- `localization_cycles`: Number of localization measurements per detection (default: 5)
- `cycle_interval`: Time between localization cycles in seconds (default: 4.0)
- `cooldown_seconds`: Minimum time between automatic localizations (default: 25.0)

Microphone array configuration is defined in `config/config.py`, including:
- Array size and microphone positions
- Sample rate and chunk duration
- TDOA calculation parameters

## API Endpoints

- `GET /api/status`: Get current system state and latest localization result
- `POST /api/trigger-localization`: Manually trigger a one-shot localization
- `POST /api/pause-classification`: Pause classification for manual localization
- `WebSocket /ws`: Real-time event stream (classification results, localization data, errors)

## Related Projects

### Localization Experiments

All localization experiments for drones, including different versions and engines we tried to optimize for continuous audio signals, are documented in the [TDOA-DOA repository](https://github.com/BP-BATradar/TDOA-DOA). This repository contains various localization algorithms, TDOA calculation methods, and multilateration approaches.

### Detection Model Experiments

Experiments with different machine learning models for drone detection (SVM, DNN, KNN, GMM, CNN, RNN) are documented in the [drone-classification repository](https://github.com/BP-BATradar/drone-classification). This repository includes model training scripts, evaluation metrics, and performance comparisons across different detection approaches.

## Project Structure

```
BATradar/
├── classification/          # Drone detection models
│   ├── models/              # Trained model files
│   ├── src/                # Training and inference code
│   └── test/               # Model evaluation scripts
├── localization/           # TDOA, DOA, multilateration algorithms
├── recording/              # Multi-device audio recording
├── config/                 # System configuration
├── frontend/               # Web interface
├── api_server.py          # FastAPI server
├── system_manager.py      # Main orchestration logic
└── localization_service.py # Localization service wrapper
```

