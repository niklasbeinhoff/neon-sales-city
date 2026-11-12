# Neon Sales City – flerspelare på webben

En 3D-stad där varje byggnad är en affär och budgeten är en boss. Spelare går med från sin egen webbläsare, sätter sin budget och stänger affärer som skjuter ner bossen på storskärmen.

All data är påhittad eller inskriven av spelarna, ligger bara i serverns minne och försvinner när servern startas om.

## Filer

| Fil | Vad den gör |
| --- | --- |
| `server.py` | Liten spelserver, bara Pythons standardbibliotek |
| `neon-sales-city-multi.html` | Storskärmen med staden (adressen `/`) |
| `play.html` | Spelarnas sida (adressen `/play`) |
| `render.yaml` | Färdig inställning för Render |
| `Dockerfile` | För andra tjänster som kör containrar |

## Köra lokalt

```bash
python3 server.py
```

Öppna `http://localhost:8765`. Andra enheter på samma nät når `http://<datorns-ip>:8765/play`, om nätet och VPN tillåter det.

## Lägga upp på Render

1. Lägg den här mappen i ett GitHub-repo. Privat går bra.
2. Logga in på render.com med GitHub.
3. Välj **New → Blueprint** och peka på repot. Render läser `render.yaml`.
4. Ange ett eget värde för `ADMIN_KEY`. Det är koden som krävs för att nollställa spelet.
5. När tjänsten är igång får du en adress som slutar på `.onrender.com`.

Utan Blueprint: **New → Web Service**, Python, byggkommando `echo ok`, startkommando `python3 server.py`, och miljövariabeln `ADMIN_KEY`.

## Använda

- Storskärm: tjänstens adress. Den visar en QR-kod till spelarsidan.
- Spelare: tjänstens adress följt av `/play`.
- Nollställ: ♻️ på storskärmen och ange `ADMIN_KEY`.

## Bra att veta

- Gratisnivån somnar efter en stunds inaktivitet. Ha storskärmen öppen så hålls den vaken; första sidladdningen efter en paus kan ta upp till en minut.
- Alla som har adressen kan gå med. Dela den bara med dem som ska spela.
- Inställningarna för Render är inte provkörda där än.
