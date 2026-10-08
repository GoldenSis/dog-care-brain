# Photos, vidéos et personnalisation

En mode compte, **Chiens** ouvre l’album privé du chien sélectionné. Les mêmes albums figurent dans **En images**. Une famille peut ajouter plusieurs photos ou vidéos, ouvrir une image en grand, lire une vidéo, télécharger l’original, choisir une photo de couverture ou retirer un média. **Prendre une photo** propose la caméra arrière lorsque le téléphone le permet ; le sélecteur de fichiers reste disponible. La capture ne démarre jamais automatiquement.

La propriétaire gère les albums de son entreprise. Une famille accède uniquement aux chiens qui lui sont actuellement attribués et aux médias enregistrés pour cette même famille. Une réattribution ne transmet jamais l’ancien album à la nouvelle famille. Les dog-sitters invités n’ont pas accès aux albums privés. Les notes audio et la galerie existante restent disponibles selon leurs autorisations habituelles. Le mode statique conserve ses fonctionnalités existantes ; les nouveaux albums et réglages publics nécessitent un compte.

Dans **Réglages → Photo de la page d’accueil**, **Changer la photo** ajoute un brouillon privé. La propriétaire choisit l’image, vérifie l’aperçu, conserve la photo entière ou ajuste le cadrage, puis enregistre explicitement pour la publier. Le cadrage initial d’une nouvelle photo conserve toute l’image afin de garder les deux sujets visibles. La photo par défaut reste publique jusqu’à l’enregistrement ; **Revenir à la photo par défaut** restaure celle-ci. Les services proposent trois visages dessinés dans l’application — terrier, carlin et dalmatien — ou une image ajoutée pour cette page. Les libellés des services restent visibles. Un album privé ne peut jamais devenir une illustration publique : il faut ajouter délibérément une image dans ces réglages.

## Formats et limites

- Photos : JPEG, PNG 8 bits non entrelacé, WebP fixe ; 12 Mio et 40 millions de pixels maximum par photo.
- Vidéos : MP4 ou MOV contenant une piste H.264, WebM VP8/VP9 ; 80 Mio maximum par vidéo. La lecture dépend aussi des codecs audio et du navigateur ; le téléchargement de l’original reste disponible.
- HEIC, HEVC/H.265, SVG et formats non reconnus sont refusés avec un message explicite. Sur un téléphone qui produit HEIC/HEVC, utiliser le réglage de capture compatible JPEG/H.264 ou exporter une copie compatible avant l’envoi. L’application ne transcode pas les fichiers.
- Par entreprise : 1 000 fichiers et 2 Gio. Retirer des médias libère le quota actif. Les copies déjà présentes dans les sauvegardes suivent la rétention de celles-ci.

Le serveur vérifie le type déclaré, la signature et la structure du conteneur, les dimensions des images, les sommes de contrôle des blocs PNG et les données PNG décompressées. Ce contrôle ne remplace pas un décodeur complet de tous les codecs vidéo. Le navigateur signale les erreurs de lecture. La progression distingue transfert et validation. Un envoi interrompu ou invalide ne crée aucune entrée ; dans une sélection multiple, les fichiers déjà confirmés restent affichés si un fichier suivant échoue.

## Stockage et API

Python 3.11 ou ultérieur est requis pour les transferts binaires SQLite ; la validation du projet utilise Python 3.12. Les originaux sont stockés comme BLOBs binaires dans `media_asset`, dans le même SQLite privé et isolé par entreprise que les autres données. Ils ne sont jamais encodés dans localStorage, une réponse JSON ou un fichier public. Un fichier temporaire privé reçoit les blocs du transfert, puis contenu et métadonnées sont enregistrés dans une transaction. Les transferts et téléchargements utilisent des blocs de 64 Kio. Le fichier temporaire disparaît après succès ou échec. La suppression retire les octets actifs, la couverture et toute sélection publique qui les utilisait, dans la même transaction.

`GET /api/media` et le champ `media` de `/api/state` contiennent les métadonnées autorisées, `covers` et les réglages `branding` pour la propriétaire. Les écritures utilisent la session, la vérification d’origine et `X-DogCare-Business`, indépendamment du numéro de révision des notes du quotidien. L’autorisation est vérifiée de nouveau après le transfert, dans la transaction d’enregistrement.

| Route | Corps / effet |
| --- | --- |
| `POST /api/media/upload?dogId=<id>` | Octets du fichier, MIME dans `Content-Type`, nom encodé URI dans `X-DogCare-Filename`. Ajoute un média privé pour la famille enregistrée du chien. |
| `POST /api/media/upload?purpose=branding` | Même transfert, image uniquement, propriétaire uniquement. Crée un brouillon privé. |
| `POST /api/media/cover` | JSON `{dogId, mediaId}` ; photo autorisée du même album, ou `null` pour retirer la couverture. |
| `POST /api/media/delete` | JSON `{id}` ; propriétaire de l’entreprise ou famille autorisée de l’album. |
| `POST /api/media/branding` | JSON `{hero, services}` ; sélection explicite de brouillons publics par la propriétaire. `hero` vaut `null` ou `{mediaId, fit, position}` ; chaque service vaut `{face}` ou `{mediaId}`. |
| `GET /api/media/content/<id>` | Original privé, vérification de l’entreprise, du rôle et de la famille ; plages HTTP prises en charge pour la lecture vidéo. |
| `GET /api/public/branding` | Uniquement les illustrations sélectionnées pour `DC_PUBLIC_BUSINESS`. |
| `GET /api/public/media/<id>` | Image accessible anonymement uniquement tant qu’elle est sélectionnée dans ces réglages publics. |

Les sauvegardes SQLite en ligne incluent les originaux et leurs métadonnées dans le même instantané, ainsi que couvertures et sélections publiques. La vérification compare tailles, empreintes SHA-256 et références avant publication ou rétention. La restauration vers un nouveau répertoire conserve ces contenus. Voir [la sauvegarde privée](private-beta-release.md).

Les tests `tests.test_media_api` et `tests.test_media_browser` utilisent exclusivement des fichiers et comptes synthétiques. Ils vérifient autorisations, transfert, rechargement, lecture, couverture, remplacement, suppression, accès public choisi et sauvegarde/restauration, ainsi que les contrôles à 1440 et 390 pixels. Les sélecteurs et captures synthétiques ne prouvent pas le comportement d’une caméra physique ou de chaque téléphone.
