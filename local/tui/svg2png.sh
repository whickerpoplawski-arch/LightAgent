#!/bin/sh
# usage: svg2png.sh in.svg out.png   （按 SVG viewBox 自动算高度，避免底部被裁）
VB=$(grep -o 'viewBox="[^"]*"' "$1" | head -1 | tr -d '"' | cut -d' ' -f3,4)
W=$(echo "$VB" | cut -d' ' -f1 | cut -d. -f1); H=$(echo "$VB" | cut -d' ' -f2 | cut -d. -f1)
printf '<html><body style="margin:0;background:#fff"><img src="file://%s" style="width:%spx;display:block"></body></html>' "$1" "$W" > /tmp/svgwrap.html
google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1.5 --window-size="$W,$H" --screenshot="$2" file:///tmp/svgwrap.html 2>/dev/null
