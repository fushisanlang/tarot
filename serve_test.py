import signal, sys
# Start Flask server on port 5002
from tarot.app import create_app
app = create_app()
print("SERVER_READY", flush=True)
app.run(host='0.0.0.0', port=5002, debug=False)
