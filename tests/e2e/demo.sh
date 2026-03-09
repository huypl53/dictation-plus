#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "Building dictation-e2e image..."
docker build -f tests/e2e/Dockerfile -t dictation-e2e .

PORT="${1:-5678}"
echo ""
echo "Starting dictation server on http://localhost:${PORT}"
echo "Press Ctrl+C to stop."
echo ""
echo "Try these commands from another terminal:"
echo ""
echo "  # Check status"
echo "  curl http://localhost:${PORT}/status"
echo ""
echo "  # Generate speech (saves WAV file)"
echo "  curl -s -X POST http://localhost:${PORT}/v1/audio/speech \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"model\": \"piper\", \"input\": \"Hello world, this is a test.\", \"voice\": \"alloy\"}' \\"
echo "    -o /tmp/hello.wav && echo 'Saved to /tmp/hello.wav'"
echo ""
echo "  # Play it (if aplay/ffplay available)"
echo "  aplay /tmp/hello.wav"
echo ""

docker run --rm -it -p "${PORT}:5678" dictation-e2e \
    python3 -c "
from dictation.stt import STTEngine
from dictation.tts import TTSEngine
from dictation.api import create_app
from dictation.pool import EnginePool
import uvicorn

print('Loading models...')
stt_pool = EnginePool(
    lambda: STTEngine(model_path='/models/vosk/vosk-model-small-en-us-0.15'),
    max_size=2,
    on_release=lambda e: e.reset(),
)
tts_pool = EnginePool(
    lambda: TTSEngine(model_path='/models/piper/en_US-lessac-medium.onnx'),
    max_size=2,
)
print('Starting server...')

app = create_app(stt_pool=stt_pool, tts_pool=tts_pool)
uvicorn.run(app, host='0.0.0.0', port=5678, log_level='info')
"
