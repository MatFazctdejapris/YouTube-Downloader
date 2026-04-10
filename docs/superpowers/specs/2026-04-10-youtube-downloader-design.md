# YouTube Playlist Downloader — Design Spec

## Objectif

Outil permettant de télécharger une playlist YouTube entière depuis un téléphone Android, via une interface web mobile-first servie par un micro-serveur Python sur le PC local (même réseau Wi-Fi).

## Architecture

```
[Android — Navigateur]  ←— Wi-Fi —→  [PC Windows — FastAPI + yt-dlp]
                                           ↓
                                      ./downloads/
```

### Fichiers du projet

| Fichier | Rôle |
|---|---|
| `server.py` | Micro-serveur FastAPI (~150 lignes). Sert l'interface, expose l'API, appelle yt-dlp. |
| `index.html` | Interface mobile-first, embarquée dans le même dossier. CSS et JS inline. |

### Dépendances

- Python 3.10+
- FastAPI + Uvicorn
- yt-dlp (installé via pip ou binaire)
- ffmpeg (pour la conversion audio)

## API

| Méthode | Endpoint | Rôle |
|---|---|---|
| `GET` | `/` | Sert `index.html` |
| `POST` | `/api/playlist` | Reçoit `{ url: string }`. Retourne la liste des morceaux (titre, durée, thumbnail, id). |
| `POST` | `/api/download` | Reçoit `{ ids: string[], format: string, quality: string, metadata: bool }`. Lance le téléchargement. |
| `GET` | `/api/status` | Retourne la progression : `{ current: int, total: int, tracks: [{ id, status, progress }] }`. Polling toutes les secondes. |
| `GET` | `/api/files` | Liste les fichiers téléchargés disponibles : `[{ name, size, url }]`. |
| `GET` | `/api/files/{filename}` | Sert le fichier pour téléchargement sur le téléphone. |

### Détail des statuts de progression

- `waiting` — en attente dans la file
- `downloading` — en cours de téléchargement
- `converting` — conversion format en cours
- `done` — terminé, fichier disponible
- `error` — échec, message d'erreur inclus

## Paramètres configurables

| Paramètre | Valeurs | Défaut |
|---|---|---|
| Format | MP3, FLAC, OPUS, M4A, MP4 | MP3 |
| Qualité audio | 128k, 192k, 256k, 320k | 320k |
| Sélection morceaux | Tout / individuel | Tout |
| Métadonnées | On / Off (titre, artiste, pochette) | On |
| Dossier destination | Chemin configurable | `./downloads` |
| Gestion doublons | Via `--download-archive` de yt-dlp | Activé |

## Interface (index.html)

Single-page, dark mode, mobile-first. Pas de framework CSS — CSS custom inline.

### Zones de l'interface

**Zone 1 — En-tête**
- Champ URL pour coller le lien playlist
- Bouton "Charger la playlist"

**Zone 2 — Paramètres (accordéon replié par défaut)**
- Dropdown format
- Dropdown qualité
- Toggle métadonnées on/off
- Champ dossier destination

**Zone 3 — Liste des morceaux**
- Checkbox par morceau + thumbnail + titre + durée
- Boutons "Tout sélectionner" / "Désélectionner"
- Bouton "Télécharger la sélection"

**Zone 4 — Progression**
- Barre de progression par morceau
- Statut global (ex: 3/15 terminés)
- Icône par statut (en attente, en cours, terminé, erreur)

**Zone 5 — Fichiers prêts**
- Liste des fichiers avec bouton "Enregistrer" individuel
- Bouton "Tout télécharger" (zip)

### Style

- Dark mode (fond sombre, texte clair)
- Gros boutons tactiles pour mobile
- Responsive : fonctionne sur petit écran Android
- Pas de framework externe, tout en inline

## Flux utilisateur

1. L'utilisateur lance `python server.py` sur son PC
2. Le terminal affiche l'adresse locale (ex: `http://192.168.1.42:8000`)
3. L'utilisateur ouvre cette URL sur son téléphone Android
4. Il colle un lien de playlist YouTube
5. L'app affiche la liste des morceaux avec thumbnails
6. Il configure format/qualité via l'accordéon (ou garde les défauts)
7. Il sélectionne les morceaux voulus
8. Il lance le téléchargement
9. Il voit la progression en temps réel
10. Une fois terminé, il télécharge les fichiers sur son téléphone via le navigateur

## Contraintes et limites

- **Même réseau Wi-Fi requis** entre le PC et le téléphone
- **PC doit rester allumé** pendant le téléchargement
- **Pas d'accès hors domicile** (serveur local uniquement)
- **yt-dlp et ffmpeg** doivent être installés sur le PC

## Hors périmètre

- Hébergement cloud / VPS
- Application mobile native
- Gestion de comptes utilisateurs
- Streaming des morceaux (on télécharge uniquement)
