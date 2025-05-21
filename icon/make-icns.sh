#!/bin/bash

# 使用方式：
# ./make-icns.sh path/to/your-icon.png

# 如果没传参数，就退出
if [ -z "$1" ]; then
  echo "❌ 用法：./make-icns.sh your-icon.png"
  exit 1
fi

ICON_SRC="$1"
BASENAME=$(basename "$ICON_SRC" .png)
ICONSET_DIR="${BASENAME}.iconset"
ICNS_FILE="${BASENAME}.icns"

if [ ! -f "$ICON_SRC" ]; then
  echo "❌ 找不到文件：$ICON_SRC"
  exit 1
fi

echo "📦 创建 $ICONSET_DIR ..."
mkdir -p "$ICONSET_DIR"

echo "🔧 生成各尺寸图标..."
sips -z 16 16     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16.png"
sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_16x16@2x.png"
sips -z 32 32     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32.png"
sips -z 64 64     "$ICON_SRC" --out "$ICONSET_DIR/icon_32x32@2x.png"
sips -z 128 128   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128.png"
sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_128x128@2x.png"
sips -z 256 256   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256.png"
sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_256x256@2x.png"
sips -z 512 512   "$ICON_SRC" --out "$ICONSET_DIR/icon_512x512.png"
cp "$ICON_SRC" "$ICONSET_DIR/icon_512x512@2x.png"

echo "🎯 生成 $ICNS_FILE ..."
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"

if [ -f "$ICNS_FILE" ]; then
  echo "✅ 成功生成 $ICNS_FILE"
else
  echo "❌ 生成失败"
  exit 1
fi

echo "🧹 清理中间文件..."
rm -r "$ICONSET_DIR"

echo "✨ 完成"
