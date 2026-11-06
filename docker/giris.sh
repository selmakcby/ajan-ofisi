#!/bin/sh
# Ajan Ofisi konteyner girişi: ofis kullanıcısıyla çalışır.
set -e
umask 027                       # yeni dosyalar: sahibi yazar, ekip okur, başkası göremez
mkdir -p /veri/gizli /veri/calisma /veri/cikti
chmod 0700 /veri/gizli 2>/dev/null || true
exec python /uygulama/sunucu.py
