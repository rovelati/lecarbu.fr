# Contabo VPS — regole di utilizzo condiviso

Documento locale per **vmi3323988** (`37.60.255.18`).  
Aggiornare **ogni volta** che si aggiunge un servizio, dominio, porta o cron.

> **Credenziali:** non scrivere password in questo file.  
> Accesso SSH: `DISCOVER/NUOVO-SERVER.ssh` + password in `DISCOVER/.new-server-passwd` (solo locale, **mai in git**).

---

## 1. Principi (obbligatori)

1. **Prima di modificare:** leggere questo file + fare inventario (`ss -tlnp`, `pm2 list`, `nginx -t`, crontab).
2. **Non toccare** servizi altrui senza motivo: ProntoFarmacie, Veterinari, ProgrammeCeSoir, Finance, Notaiogiusto, EPG DE, ecc.
3. **Niente `pm2 delete all`**, `systemctl stop nginx/postgresql`, drop database, `certbot delete`, rsync `--delete` su `/var/www/<altro-progetto>`.
4. **Un servizio = una porta locale dedicata** (127.0.0.1 o 0.0.0.0 solo se necessario); registrare la porta qui sotto **prima** del deploy.
5. **Nginx:** nuovo sito = nuovo file in `/etc/nginx/sites-available/` + symlink in `sites-enabled/` + `nginx -t` + `systemctl reload nginx` (mai restart brusco se evitabile).
6. **SSL:** Let's Encrypt via certbot; non duplicare certificati per lo stesso `server_name`.
7. **Segreti:** env in PM2 / file `.env` sul server; non committare; non stampare in log pubblici.
8. **Cron:** molti job ProntoFarmacie/Veterinari sono **produzione**; non spostare orari senza accordo.
9. **PostgreSQL 16** è **condiviso** (localhost:5432): un DB per progetto, utente dedicato, no `DROP DATABASE` senza backup.
10. **Backup** prima di cambiamenti rischiosi (config nginx, PM2, postgrest, DB).

---

## 2. Profilo macchina (snapshot)

| Campo | Valore |
|--------|--------|
| Provider | Contabo |
| Hostname | `vmi3323988` |
| IP | `37.60.255.18` |
| OS | Ubuntu 24.04 LTS |
| RAM | ~12 GiB |
| Disco `/` | ~193 GiB (verificare con `df -h`) |
| Docker | **Non in uso** |
| Web front | **nginx** (80/443) |
| App runtime | **Node.js + PM2** |
| DB locale | **PostgreSQL 16** (solo localhost) |
| API DB | **PostgREST** (systemd) per alcuni progetti |

Ultimo inventario documentato: **2026-10-11** (solo lettura SSH).

---

## 3. Domini nginx attivi (`sites-enabled`)

| Dominio | Backend tipico | Note |
|---------|----------------|------|
| `prontofarmacie.it` / `www` / `lavoro` | Astro SSR `:4310`, PostgREST `:4312` | Cron intensivi turni/lavoro |
| `veterinari.org` / `www` | Astro `:4321`, PostgREST `:3011` | Cron enrichment / lead marketing |
| `www.notaiogiusto.it` | Astro `:4330` | |
| `programmecesoir.fr` / `www` | PM2 cluster → `:3001` | DB `programmecesoir` |
| `baumicio.it` | (config dedicata) | |
| `finance.realtimediscover.com` | Next `:3010`, API uvicorn `:8010` | Utente Linux `finance`, path `/srv/finance` |
| `gsc.realtimediscover.com` | static `/var/www/gsc.realtimediscover.com/public`, API PM2 → `:8787` | Staging RealTime Discover (OAuth); deploy `scripts/deploy-gsc-contabo.sh` |
| `uktvtonight.co.uk` / `www` | static Astro `/var/www/uktvtonight.co.uk/dist` | DB `uktvtonight`, cron 05:30 daily |

Siti presenti sotto `/var/www` ma **non** necessariamente in `sites-enabled`:  
`123programmitv.it`, `fernsehheute.de`, `codebase`, ecc. — verificare prima di assumere che siano offline.

---

## 4. Tabella porte (non riusare senza aggiornare questo file)

| Porta | Bind | Servizio | Proprietario progetto |
|-------|------|----------|------------------------|
| 22 | 0.0.0.0 | SSH | sistema |
| 80 / 443 | 0.0.0.0 | nginx | sistema |
| 3001 | 127.0.0.1 | ProgrammeCeSoir (PM2 cluster) | programmecesoir.fr |
| 3010 | 0.0.0.0 | Finance frontend (Next) | finance.realtimediscover.com |
| 3011 | 127.0.0.1 | PostgREST veterinari | veterinari.org |
| 4310 | 127.0.0.1 | ProntoFarmacie Astro SSR | prontofarmacie.it |
| 4312 | 127.0.0.1 | PostgREST prontofarmacie | prontofarmacie.it |
| 4321 | 0.0.0.0 | Veterinari Astro SSR | veterinari.org |
| 4330 | 127.0.0.1 | Notaiogiusto Astro SSR | notaiogiusto.it |
| 5432 | 127.0.0.1 | PostgreSQL 16 | condiviso |
| 8010 | 127.0.0.1 | Finance API (uvicorn) | finance.realtimediscover.com |

### Porte riservate (pianificate — non occupare)

| Porta | Uso previsto | Progetto |
|-------|----------------|----------|
| **8787** | API Node RealTime Discover (OAuth GSC) — **in uso** PM2 `realtimediscover-gsc-api` | gsc.realtimediscover.com |
| **3012** | (alternativa se 8787 non va bene) | discorealtime-supabase |

Prima di usare un’altra porta: `ss -tlnp | grep :PORTA`.

---

## 5. PM2 (processi Node)

| Nome PM2 | Path deploy | Porta env |
|----------|-------------|-----------|
| `prontofarmacie` | `/var/www/prontofarmacie.it/app` | 4310 |
| `veterinari-org` | `/var/www/veterinari-org` | 4321 |
| `notaiogiusto-it` | `/var/www/notaiogiusto-it` | 4330 |
| `programmecesoir` | `/var/www/programmecesoir.fr/astro` | 3001 (×2 istanze cluster) |
| `realtimediscover-gsc-api` | `/var/www/gsc.realtimediscover.com/api` | 8787 |

Regole PM2:

- Nome processo: `{brand}-{tld}` o già consolidato (non rinominare senza update doc).
- `pm2 save` dopo aggiunta; verificare startup (`pm2 startup` già configurato sul server).
- Log: `pm2 logs <name> --lines 100` — non cancellare log altrui.

---

## 6. PostgreSQL — database applicativi

Database rilevati (non eliminare):

- `prontofarmacie`
- `veterinari_org`
- `programmecesoir`
- `fernsehheute`
- `programmitv`
- `stock_tracker`
- `uktvtonight` (proprietario: uktvtonight_app - uktvtonight.co.uk)

Nuovo progetto:

1. Creare **utente** + **database** dedicati.
2. Permessi minimali.
3. Aggiungere riga in §6 di questo file.

---

## 7. PostgREST (systemd)

| Unit | Config | Porta |
|------|--------|-------|
| `postgrest-prontofarmacie.service` | `/etc/postgrest-prontofarmacie.conf` | 4312 |
| `postgrest-veterinari.service` | `/etc/postgrest-veterinari.conf` | 3011 |

Modifiche: `systemctl edit` o edit config + `systemctl restart postgrest-*` solo in finestra concordata (ProntoFarmacie/Veterinari in traffico).

---

## 8. Cron di produzione (root)

Timezone crontab: **Europe/Paris**.

Gruppi principali (non disabilitare senza capire l’impatto):

- **ProntoFarmacie:** turni federfarma/regioni, pharmaround batch, sitemap, job alerts, lavoro/spider ogni 4h.
- **Veterinari:** enrichment prioritario (06:00), lead marketing (08:00, 13:00).
- **Fernsehheute DE:** EPG/tmdb/rebuild astro (04:xx–05:xx).
- **UK TV Tonight:** Rebuild EPG mattutino (05:30), refresh EPG e ping IndexNow serale pre-prime time (17:30 = 16:30 UK), ping notturno domani (23:30 = 22:30 UK). Log in `/var/log/uktvtonight/`.
- **PrezzoBenza (prezzobenza.it):** Rebuild notturno (02:30), ingestione dati MIMIT, deploy Cloudflare Pages e ping IndexNow. Log in `/var/log/prezzobenza-rebuild.log`.

Prima di aggiungere cron RealTime Discover: usare `flock` + log dedicato sotto `/var/log/realtimediscover/`.

---

## 9. Checklist — aggiungere un **nuovo servizio**

Copiare e compilare per ogni deploy (es. RealTime Discover API):

```text
[ ] Nome servizio:
[ ] Dominio(i):
[ ] Porta locale scelta (libera in §4):
[ ] Directory codice (/var/www/... o /srv/...):
[ ] Runtime (PM2 / systemd / static):
[ ] DB necessario? (sì/no — Supabase cloud vs Postgres locale)
[ ] File nginx: /etc/nginx/sites-available/________
[ ] Certbot: certificato nuovo o SAN esistente?
[ ] Env file path (permessi 600):
[ ] Healthcheck URL:
[ ] Owner / contatto:
[ ] Data deploy:
[ ] Rollback plan (backup path + comando restore):
```

Dopo il deploy: **aggiornare §3, §4, §5, §6** in questo file.

---

## 10. RealTime Discover — note specifiche (pianificazione)

- **Frontend attuale:** Hostinger (`www.realtimediscover.com`) — statico.
- **Su Contabo già presente:** `finance.realtimediscover.com` (non confondere stack/porte).
- **Obiettivo probabile:** API OAuth Google (`/api/auth/*`) su Contabo, porta **8787** (o proxy nginx su sottodominio tipo `api.realtimediscover.com`).
- **Non** mischiare env Finance (`/srv/finance`) con Discover.
- **Supabase dati dashboard:** resta cloud; sul VPS serve solo auth/session + eventuale proxy.

Proposta dominio API (da confermare prima del deploy):

- `api.realtimediscover.com` → `127.0.0.1:8787`
- Redirect OAuth Google: `https://api.realtimediscover.com/api/auth/google/callback`

---

## 11. Comandi utili (solo diagnostica)

```bash
# SSH (da macOS, password in .new-server-passwd)
ssh root@37.60.255.18

pm2 list
ss -tlnp
nginx -t && systemctl status nginx
systemctl status postgresql@16-main
crontab -l
certbot certificates
df -h && free -h
```

---

## 12. Storico modifiche a questo documento

| Data | Autore | Modifica |
|------|--------|----------|
| 2026-10-11 | Inventario iniziale | Creazione regole + mappa servizi esistenti |

---

## 13. File locali correlati (DISCOVER)

| File | Contenuto |
|------|-----------|
| `NUOVO-SERVER.ssh` | Comando SSH (`root@37.60.255.18`) |
| `.new-server-passwd` | Password root ( **non committare** ) |
| `discorealtime-supabase/` | Repo RealTime Discover |
| `codebase/` | Altri sorgenti (es. spider veterinari) |

Suggerimento: aggiungere a `.gitignore` globale o personale:

```gitignore
.new-server-passwd
NUOVO-SERVER.ssh
```

(se non servono in repo).
