SAMPLE_RATE = 16000
CHUNK_DURATION = 1.0
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

SPEED_OF_SOUND = 343.0

ARRAY_SIZE = 3.0
MIC_POSITIONS = {
    'bottom_left': (0.0, 0.0, 0.0),
    'bottom_right': (ARRAY_SIZE, 0.0, 0.0),
    'top_left': (0.0, ARRAY_SIZE, 0.0),
    'top_right': (ARRAY_SIZE, ARRAY_SIZE, 0.0)
}

MIC_ORDER = [
    "bottom_left",
    "bottom_right",
    "top_left",
    "top_right",
]

REFERENCE_MIC_INDEX = 0
MAX_TDOA = ARRAY_SIZE * 1.4142 / SPEED_OF_SOUND

USE_GCC_PHAT = True
CORRELATION_MAX_LAG = int(MAX_TDOA * SAMPLE_RATE * 1.5)

MIC_BIAS_SECONDS = {
    'bottom_left': 0.0,
    'bottom_right': 0.0,
    'top_left': 0.0,
    'top_right': 0.0,
}

DRONE_FUNDAMENTAL_RANGE = (80, 400)
DRONE_NUM_HARMONICS = 12
DRONE_HARMONIC_BANDWIDTH = 15.0

DRONE_FREQUENCY_BANDS = [
    (80, 200, 1.0),
    (200, 400, 0.9),
    (400, 800, 0.8),
    (800, 1600, 0.6),
    (1600, 3200, 0.4),
]

DRONE_SNR_THRESHOLD = 3.0

DRONE_HIGHPASS_FREQ = 60.0
DRONE_NOTCH_FREQS = [50.0, 60.0]
DRONE_NOTCH_Q = 30.0

