# Gemini Desk — Flask, Tailwind CSS v4, MySQL et Gemini

Application de conversation locale avec historique MySQL, catégories spécialisées, import de fichiers, analyse SQL, métriques de tokens et journalisation.

## Fonctionnalités

- Nouvelle conversation, effacement et suppression.
- Historique permanent dans la barre latérale.
- Catégories : éducation, droit, assistance médicale, maison et programmation.
- Mode généraliste par défaut.
- Import PDF, images, SQL, Excel (`.xlsx`/`.xls`), Word (`.docx`), TXT et CSV.
- Analyse statique des fichiers SQL avec score et recommandations.
- Export d'une conversation au format TXT (`user : ...`, `assistant : ...`).
- Tokens d'entrée, de sortie et total pour chaque réponse.
- Temps de réponse Gemini en millisecondes.
- Modes combinables avant envoi : réponse concise, analysée et instantanée.
- Marquage de confiance auto-évalué : rouge pour « sûr », bleu pour « à vérifier ».
- Rendu Markdown sécurisé des réponses : titres, listes, tableaux, liens et blocs de code.
- Interface type Messenger : messages utilisateur à droite en bleu, réponses Gemini à gauche.
- Journal des erreurs dans MySQL et dans `logs/app.log`.
- MySQL 8.4 et phpMyAdmin via Docker Compose.

## Installation rapide sous Windows

Prérequis : Python 3.11+, Node.js LTS, Docker Desktop.

1. Double-cliquez sur `setup_windows.bat`.
2. Ouvrez `.env` et remplacez `GEMINI_API_KEY` par votre clé Google AI Studio.
3. Double-cliquez sur `start_all_windows.bat`.

Adresses :

- Application : <http://127.0.0.1:5000>
- phpMyAdmin : <http://127.0.0.1:8080>

Identifiants phpMyAdmin de développement :

- Serveur : `mysql`
- Utilisateur : `gemini`
- Mot de passe : `gemini_dev_password`

Modifiez ces valeurs dans `.env` avant un déploiement réel.

## Commandes manuelles

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
npm install
npm run build:css
docker compose up -d
python run.py
```

Pendant le développement Tailwind :

```powershell
npm run dev:css
```

## Base de données

SQLAlchemy crée automatiquement les tables `conversations`, `messages` et `error_logs`. Les données MySQL sont conservées dans le volume Docker `gemini_mysql_data`, même après `docker compose down`.

Les fichiers SQL volumineux sont enregistrés dans `messages.attachment_text` en `MEDIUMTEXT` (jusqu'à environ 16 Mo). Au redémarrage, Flask élargit automatiquement une ancienne colonne `TEXT` sans supprimer l'historique. En dernier recours, exécutez `database/upgrade_attachment_text.sql` dans phpMyAdmin.

La confiance affichée est une auto-évaluation du modèle : elle aide à repérer les affirmations à vérifier, mais ne prouve pas qu'une information est vraie. Pour les sujets médicaux, juridiques ou sensibles, vérifiez toujours les sources importantes.

Pour supprimer aussi les données de développement :

```powershell
docker compose down -v
```

Attention : cette dernière commande supprime définitivement l'historique MySQL.

## Import de fichiers

- Les documents texte sont extraits localement.
- Les images et PDF scannés sont envoyés à Gemini en entrée multimodale.
- Les fichiers SQL reçoivent un contrôle statique avant l'analyse par Gemini.
- La taille maximale est définie par `MAX_UPLOAD_MB` dans `.env`.

Le format Word historique `.doc` n'est pas accepté : enregistrez-le en `.docx`.

## Sécurité

Le projet est prévu pour un environnement local. Avant une mise en production, ajoutez une authentification, changez tous les secrets, désactivez `FLASK_DEBUG`, placez l'application derrière HTTPS et limitez l'accès à phpMyAdmin.

Au 20 octobre 2026, `npm audit` signale une alerte de déni de service dans `braces`, dépendance transitive du mode surveillance de `@tailwindcss/cli`. Elle concerne uniquement l'outil de compilation en développement, pas le CSS généré ni le serveur Flask. La CLI est verrouillée en version 4.3.0 ; mettez-la à jour lorsqu'une version corrigée de sa chaîne de dépendances sera publiée.
