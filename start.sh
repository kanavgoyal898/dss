#!/bin/bash

PORT=8100
COORDINATOR_URL="https://dss-coordinator.onrender.com"

cd "$(dirname "$0")"

pip3 install -r dss/requirements.txt

cleanup() {
  echo "Cleaning up..."
  [[ ! -z "$TUNNEL_PID" ]] && kill $TUNNEL_PID 2>/dev/null
  [[ ! -z "$NODE_PID" ]] && kill $NODE_PID 2>/dev/null
  [[ ! -z "$UI_PID" ]] && kill $UI_PID 2>/dev/null
  rm -f tunnel.log dss/node.log dss/ui/ui.log
  exit 0
}

trap cleanup SIGINT SIGTERM

kill -9 $(lsof -ti :$PORT) 2>/dev/null

cd dss
python3 run_node.py --port $PORT --coordinator $COORDINATOR_URL > node.log 2>&1 &
NODE_PID=$!
cd ..

for i in {1..10}; do
  nc -z localhost $PORT && break
  sleep 1
done

cloudflared tunnel --url http://localhost:$PORT > tunnel.log 2>&1 &
TUNNEL_PID=$!

TUNNEL_URL=""
for i in {1..15}; do
  sleep 1
  TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' tunnel.log | head -n 1)
  [[ -n "$TUNNEL_URL" ]] && break
done

if [[ -z "$TUNNEL_URL" ]]; then
  echo "Failed to get Cloudflare URL"
  cleanup
fi

HOST=$(echo $TUNNEL_URL | sed 's|https://||')
echo "Tunnel URL: $TUNNEL_URL"

kill $NODE_PID 2>/dev/null
export DSS_ADVERTISED_HOST=$HOST
export NEXT_PUBLIC_COORDINATOR_URL=$COORDINATOR_URL
export NEXT_PUBLIC_NODE_URL=$TUNNEL_URL

cd dss
python3 run_node.py --port $PORT --coordinator $COORDINATOR_URL > node.log 2>&1 &
NODE_PID=$!
cd ..

RENDER_URLS=(
"https://dss-coordinator.onrender.com/"
"https://dss-peer.onrender.com/"
"https://dss-peer-1.onrender.com/"
"https://dss-peer-2.onrender.com/"
"https://dss-peer-3.onrender.com/"
"https://dss-peer-4.onrender.com/"
"https://dss-peer-5.onrender.com/"
"https://dss-peer-6.onrender.com/"
)

echo "Waking up Render free-tier apps in parallel..."

PREWARM_PIDS=()
for url in "${RENDER_URLS[@]}"; do
  (
    for i in {1..20}; do
      status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
      if [[ "$status" -ge 100 && "$status" -lt 500 ]]; then
        break
      else
        echo "Waiting for $url..."
        sleep 3
      fi
    done
  ) &
  PREWARM_PIDS+=($!)
done

for pid in "${PREWARM_PIDS[@]}"; do
  wait $pid
done
echo "All Render apps pre-warm complete."

cd dss/ui

if [ ! -d "node_modules" ]; then
  echo "Running npm install..."
  npm install --no-audit --no-fund --prefer-offline
  if [ $? -ne 0 ]; then
    echo "npm install failed, check your network or package.json"
    cd ../..
    cleanup
  fi
else
  echo "node_modules already exists, skipping npm install."
fi

npm run dev > ui.log 2>&1 &
UI_PID=$!
cd ../..

echo "UI started (PID $UI_PID). Waiting for it to be ready..."
for i in {1..15}; do
  sleep 1
  nc -z localhost 3000 && echo "UI is up at http://localhost:3000" && break
done

BROWSER_URLS=(
"https://dss-coordinator.vercel.app/admin"
"https://dss-peer.vercel.app/node"
"http://localhost:3000/node"
)

echo "Opening browser tabs..."
for url in "${BROWSER_URLS[@]}"; do
  xdg-open "$url" 2>/dev/null || open "$url" 2>/dev/null
done

echo ""
echo "All services running. Press Ctrl+C to stop."
echo "Logs: dss/node.log | tunnel.log | dss/ui/ui.log"
echo ""
wait $NODE_PID
