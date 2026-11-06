#!/bin/sh
# Ajan Ofisi konteyner girişi: ofis kullanıcısıyla çalışır.
set -e
umask 027                       # yeni dosyalar: sahibi yazar, ekip okur, başkası göremez
mkdir -p /veri/gizli /veri/calisma /veri/cikti
chmod 0700 /veri/gizli 2>/dev/null || true
# Klasör sahiplikleri imajdan named volume'a gelir; bind mount kullanılırsa gelmez: anlaşılır biçimde dur.
if [ ! -w /veri/gizli ] || [ ! -d /veri/ev-ajan ] || [ ! -w /veri/calisma ]; then
  echo "HATA: /veri izinleri eksik. docker-compose.yml'deki named volume'u (ofis-veri) kullan; bind mount desteklenmez." >&2
  exit 1
fi
exec python /uygulama/sunucu.py
