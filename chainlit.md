# OllamaHybridBot

![PBN ARCHITECT](public/logo_pbn.png?v=14)

Interface de chat développée par **PBN ARCHITECT**. Vous conversez avec des modèles Ollama (sur votre machine ou dans le cloud), avec la possibilité d'enrichir vos questions avec le web, des documents ou des images.

## Premiers pas

À l'ouverture, des **`starters`** proposent des exemples : 
- **Actualités IA,** 
- **Résumé de PDF,** 
- **Explication de code,** 
- **Analyse d'image.** 

Cliquez sur l'un d'eux pour préremplir le message, ou écrivez directement dans la zone de saisie.

L'icône **`engrenage`** ouvre les réglages : choix du modèle, température, top P et limite de tokens. Ces préférences sont conservées pour votre compte lorsque la connexion est activée.

Pour démarrer une conversation vierge, utilisez l'icône **`crayon`** en haut à gauche.

## Poser une question

Tapez votre message et envoyez. La réponse est produite par le modèle sélectionné dans les réglages.

Dans la liste des modèles, le préfixe indique où il s'exécute :

| Préfixe | Signification |
| --- | --- |
| `[local]` | Votre machine |
| `[cloud]` | Cloud Ollama |
| `[vision local]` | Vision sur votre machine |
| `[vision cloud]` | Vision dans le cloud |

Seuls les modèles de conversation apparaissent. Vous n'avez pas à gérer les modèles d'embedding ou de transcription : ils sont filtrés.

## Recherche web

Activez le bouton **`globe`** avant d'envoyer. L'application cherche des pages en lien avec votre question, puis rédige une synthèse avec des renvois numérotés `[1]`, `[2]`, etc. Cliquez sur un numéro pour ouvrir la source.

Utilisez ce mode pour l'actualité, la veille ou toute question qui demande des informations récentes. Le panneau **`Tasks`** montre l'avancement pendant la recherche.

## Documents et images

**`Documents`** : PDF, Markdown ou texte. Joignez le fichier (jusqu'à 5 fichiers, 50 Mo chacun), puis posez votre question : résumé, points clés, recherche d'information dans le contenu. Les PDF doivent contenir une couche texte (pas seulement une image scannée).

**`Images`** : PNG ou JPG. Joignez l'image et demandez une description, une analyse ou une lecture de détail. Si le modèle choisi ne gère pas la vision, l'application bascule seule vers un modèle adapté.

Vous pouvez combiner document, image et recherche web dans le même message. Le panneau Tasks suit chaque étape.

## Vos conversations

Si vous êtes connecté avec un compte, vos fils apparaissent dans la **barre latérale**. Vous retrouvez l'historique d'une session à l'autre.

**`Favoris`** : cliquez sur l'étoile d'un de vos messages pour le garder sous la main. Vous pourrez le réutiliser depuis la zone de saisie.

**`Partage`** : menu ⋯ d'un fil, puis « Partager ». Le lien ouvre la conversation en lecture seule. Même menu pour retirer le partage.

Sans connexion, les conversations ne sont pas enregistrées : chaque visite repart de zéro.

## Connexion

Lorsque l'authentification est activée, identifiant et mot de passe vous sont communiqués par l'administrateur.