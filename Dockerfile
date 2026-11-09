# Ajan Ofisi · sunucu sürümü (Docker Compose ile: docker compose up -d)
FROM python:3.12-slim

ARG CLAUDE_CODE_SURUM=latest
ARG OPENCODE_SURUM=latest
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 LANG=C.UTF-8 \
    OFIS_VERI=/veri OFIS_HOST=0.0.0.0 OFIS_SUNUCU=1 OFIS_TERMINAL_KOPRUSU=0 \
    OFIS_PENCERE_BEKLE=0 DISABLE_AUTOUPDATER=1 OPENCODE_DISABLE_AUTOUPDATE=1

# Node + Claude Code ve Opencode (ajanlar `claude -p` ya da `opencode run` ile koşar), sudo (ajan kullanıcısına geçiş), git, tzdata (TZ)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg sudo git tzdata \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_SURUM}" "opencode-ai@${OPENCODE_SURUM}" \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* /root/.npm

# Kullanıcılar: uygulama "ofis", ajanların claude/opencode süreçleri "ajan" (gizli dizini okuyamaz); ortak grup "ekip".
# sudoers: ofis yalnız claude ve opencode ikililerini ajan olarak çalıştırabilir (parolasız, ortamdan yalnız izinli değişkenler).
RUN groupadd -g 1500 ekip \
 && useradd -m -u 1000 -G ekip ofis \
 && useradd -m -u 1001 -G ekip ajan \
 && echo "ofis ALL=(ajan) NOPASSWD:SETENV: $(command -v claude)" > /etc/sudoers.d/ofis-ajan \
 && echo "ofis ALL=(ajan) NOPASSWD:SETENV: $(command -v opencode)" >> /etc/sudoers.d/ofis-ajan \
 && chmod 0440 /etc/sudoers.d/ofis-ajan \
 && visudo -cf /etc/sudoers.d/ofis-ajan

# Veri volume'u: klasörler ve sahipleri imajda kurulur; named volume ilk oluşturulurken bunları devralır.
RUN mkdir -p /veri/gizli /veri/calisma /veri/cikti /veri/ev-ajan \
 && chown ofis:ekip /veri /veri/calisma /veri/cikti && chmod 2750 /veri && chmod 2770 /veri/calisma /veri/cikti \
 && chown ofis:ofis /veri/gizli && chmod 0700 /veri/gizli \
 && chown ajan:ajan /veri/ev-ajan && chmod 0700 /veri/ev-ajan

WORKDIR /uygulama
COPY . /uygulama
USER ofis
EXPOSE 8796
VOLUME ["/veri"]
ENTRYPOINT ["sh", "/uygulama/docker/giris.sh"]
