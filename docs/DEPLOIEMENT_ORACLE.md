# Déploiement sur Oracle VPS avec Caddy

Cible suggérée : `https://mercier.arvimah.top`. Le projet peut cohabiter avec Gyma sur le même VPS : il utilise son propre conteneur, sa propre base SQLite et le port local **8091**. Avant tout changement, vérifie que ce port est libre (`ss -ltn | rg ':8091'`) et conserve la configuration Caddy existante.

## 1. Les informations à réunir

- Adresse publique du VPS et accès SSH avec Docker Compose.
- DNS : un enregistrement `A` pour `mercier.arvimah.top` pointant vers le VPS (et un `AAAA` uniquement si IPv6 fonctionne).
- Serveur SMTP et compte d'envoi autorisé, avec mot de passe d'application/secret, pour la confirmation des comptes et les liens d'achat.
- Nom des **trois vrais tiramisus**, règle de gain, seuil, récompense, éventuelles durées de validité ; Mercier doit les approuver.
- Identité légale et adresse de contact de la pâtisserie, ainsi que sa politique de conservation des données, à renseigner avant ouverture.

## 2. Installer le projet

Copie l'archive reçue sur le VPS et décompresse-la dans `/srv/mercier` (le répertoire doit contenir `compose.yaml`, `Dockerfile` et `manage.py`). Depuis ce répertoire :

```bash
cd /srv/mercier
cp .env.example .env
openssl rand -hex 32
nano .env
chmod 600 .env
```

Dans `.env`, remplace `SECRET_KEY` par la chaîne aléatoire imprimée, renseigne SMTP, `CONTACT_EMAIL` et `BUSINESS_IDENTITY`, puis vérifie :

```text
DEBUG=0
ALLOWED_HOSTS=mercier.arvimah.top
PUBLIC_URL=https://mercier.arvimah.top
TRUST_PROXY_IP=1
```

Ne colle jamais ton mot de passe SMTP ou `SECRET_KEY` dans une conversation ou un dépôt Git. `TRUST_PROXY_IP=1` suppose que le conteneur est joignable uniquement par le proxy Caddy de confiance ; le port publié est lié à l'interface locale du VPS.

Démarre et initialise :

```bash
docker compose build
docker compose up -d
docker compose exec app python manage.py migrate --noinput
docker compose exec app python manage.py seed_mercier
docker compose exec app python manage.py createsuperuser
docker compose exec app python manage.py check --deploy
docker compose ps
```

La première vérification de santé échoue avant `migrate` ; elle doit repasser au vert ensuite. `check --deploy` peut afficher les avertissements W005 et W021 : HSTS n’est volontairement pas étendu à tous les sous-domaines d’`arvimah.top` ni inscrit au préchargement tant que leur configuration HTTPS n’a pas été contrôlée. `createsuperuser` sert à créer **le compte de Mercier** ; n'utilise pas ton propre compte administrateur pour son activité quotidienne si plusieurs personnes doivent intervenir. Les comptes clients n'ont pas le rôle staff.

## 3. Brancher Caddy

Si Caddy fonctionne **directement sur l'hôte**, ajoute le bloc suivant à son Caddyfile en conservant tous les domaines existants :

```caddyfile
mercier.arvimah.top {
    reverse_proxy 127.0.0.1:8091
}
```

Teste ensuite la configuration (`caddy validate --config /etc/caddy/Caddyfile`) et recharge le service (`sudo systemctl reload caddy`). Ajuste le chemin du Caddyfile si ton installation diffère.

Si ton Caddy fonctionne **dans un conteneur Docker** (comme cela peut être le cas pour Gyma), `127.0.0.1` dans le conteneur Caddy ne désigne pas le VPS. Connecte ce conteneur au réseau créé par Compose, puis utilise le nom stable du conteneur Mercier :

```bash
docker network ls
docker network connect mercier_default NOM_DU_CONTENEUR_CADDY
```

Ajoute alors dans le Caddyfile de ce conteneur :

```caddyfile
mercier.arvimah.top {
    reverse_proxy mercier-web:8000
}
```

Valide et recharge Caddy **selon la méthode de ton déploiement actuel**. N'ajoute pas un second service Caddy sur les ports 80/443 déjà utilisés. Après une recréation du conteneur Caddy, vérifie qu'il est toujours rattaché au réseau `mercier_default`. Le nom du réseau dépend du nom du dossier/projet Compose ; contrôle-le avec `docker network ls`.

## 4. Vérifier avant d'ouvrir aux clients

```bash
curl -i https://mercier.arvimah.top/sante/
docker compose logs --tail=100 app
```

Résultat attendu : `HTTP 200` et `{"status":"ready"}`. Inscris un compte test, reçois et ouvre le mail, présente son QR code, crédite un achat depuis `/atelier/`, génère un code, vérifie qu'il ne fonctionne qu'une fois et teste la remise d'une récompense. Sur Mercier, vérifie les produits et le texte de la récompense **avant** de communiquer l'URL.

Si SMTP ne fonctionne pas, les clients peuvent créer un compte mais ne peuvent pas confirmer leur adresse et donc utiliser la carte. Vérifie d'abord les paramètres SMTP, les éventuelles restrictions de sortie du VPS et l'adresse d'expédition autorisée.

## 5. Sauvegardes, mises à jour et retour arrière

La base persistante vit dans le volume Compose `mercier_data`. Le code n'y est pas mélangé. Pour produire une copie cohérente pendant que le site tourne :

```bash
mkdir -p backups
docker compose exec -T app python scripts/backup.py /app/data/mercier-backup.sqlite3
docker compose cp app:/app/data/mercier-backup.sqlite3 ./backups/mercier-backup.sqlite3
```

Conserve aussi une copie **hors du VPS** et teste la restauration sur un environnement isolé. Une sauvegarde restée uniquement sur le VPS ne protège pas contre sa perte. Avant une mise à jour, fais une sauvegarde, puis :

```bash
docker compose build
docker compose up -d
docker compose exec app python manage.py migrate --noinput
docker compose exec app python manage.py check --deploy
```

Les migrations doivent être exécutées après chaque version qui en ajoute. Pour restaurer une ancienne base, arrête l'application, identifie le volume exact avec `docker volume ls`, replace une copie validée dans ce volume avec des droits d'accès pour l'utilisateur `mercier` (UID 10001), puis redémarre. Effectue cette opération pendant une fenêtre de maintenance : toute vente enregistrée depuis la sauvegarde serait perdue.

## Fonctionnement et sécurité

- Conserve `DEBUG=0`, TLS actif et le port `8091` non exposé publiquement.
- Garde `.env` privé ; ne mets pas la base SQLite sur GitHub.
- Mets à jour l'image Python et les dépendances régulièrement, puis exécute les tests et `check --deploy`.
- La recherche par caméra fonctionne sur les navigateurs qui exposent `BarcodeDetector`, sous HTTPS. Sinon Mercier peut saisir l'e-mail du client.
- Le domaine, l'identité de la pâtisserie, les règles de fidélité et les coordonnées de contact restent à confirmer avec Mercier avant publication.
