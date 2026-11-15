# Für den Imker 
# Erkennung Vespa-Velutina über WhatsApp

Für eine Meldung von Sichtungen bleibt immer die Unsicherheit was eigentlich gesehen wurde und ob dies in Verbindung mit der VV steht.

Um die Bevölkerung bei der Suche nach Vespa Velutina und deren Nestern werden üblicherweise Flyer verteilt. Hierauf sind QR-Codes mit Links zum Meldeportal des HLNUG (Hessen) oder zum lokalen Imkerverein aufgedruckt. Mittlerweile sind aber auch Links zu Whatsapp-Accounts weit verbreitet.

All dies bedeutet, zumindest für den Inhaber der Whatsapp-Nummer oder den Ehrenamtlichen beim Imkerverein manuelle Arbeit bei der Beuurteilung der Bilder.
Was also liegt näher die Meldung über Whatsapp und die Erkennung automatisiert über ein KI laufen zu lassen ?

Hierfür gibt es diverse Möglichkeiten, von denen ich mich für "Velu DEtect" (https://universe.roboflow.com/vespavelutina/velu-detect) entschieden habe.

Im Prinzip teilt sich das Ganze in 3 Bereiche auf:
1. Ein eigener (v)Server, öffentlich erreichbar und unser Arbeitstier.
2. Ein Account (free) bei RoboFlow (https://app.roboflow.com/)
3. Ein META-Business-Account für den WhatsApp-Teil 


## Der eigene Server und dessen Konfiguration

Im Prinzip tut es hier jeder noch so kleine Linux-Server der im Internet offentlich erreichbar ist.
Aber auch ein schon vorhandener Server, der z.B. für die Vereins-Webseite genutzt wird, reicht schon aus.

Shared-Hosting wird aber wohl eher nicht funktionieren.
Sollte das jemand so aufsetzen,, dann gerne ein Update mit Beschreibung an mich.

### Server Konfiguration

Wir gehen also von einem funktionierden Linux-vServer, hier unter Ubuntu, aus.

#### Basics installieren

	apt update
    apt install -y python3-venv python3-pip
	apt install -y nginx certbot python3-certbot-nginx 

#### Benutzer anlegen

    adduser velutina
    
#### Aktuellen Benutzer einrichten und vorbereiten
    
    - Benutzer und Verzeichnisse anlegen
    sudo su - velutina
    mkdir -p ~/velutina-bot/bilder

    - Code holen
    git clone https://github.com/dirkheitzmann/velutina-bot

    - Umgebung einrichten
    cd ~/velutina-bot

    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi uvicorn requests python-dotenv

    - Datei mit Umgebungsvariablen erstellen
    cp .env.template .env


#### nginx konfigurieren

    sudo ufw allow 'Nginx Full'

    sudo cp /home/velutina/velutina-bot/server-config/velutina-bot.nginx-config /etc/nginx/sites-available/velutina-bot
    sudo ln -s /etc/nginx/sites-available/velutina-bot /etc/nginx/sites-enabled/

    - nginx config auf euren Server  anpassen
    sudo vi /etc/nginx/sites-available/velutina-bot

    - nginx Konfiguration testen und ggfs. laden
	sudo nginx -t
	sudo systemctl reload nginx

    - SSL-Certificate für nginx konfigurieren (lassen)
	sudo certbot --nginx -d hornisse.euer-imkerverein.de

	Letzeres passt die nginx config auch für https und port 443 an.



#### Systemd-Service

Damit der Bot automatisch mit dem Server startet und bei einem Absturz sofort neu lädt, erstellt ihr einen Systemd-Service (sudo nano /etc/systemd/system/velutina-bot.service).

Dienst einrichten, aktivieren und starten:

    sudo cp /home/velutina/velutina-bot/server-configi/velutina-bot.service /etc/systemd/system/velutina-bot.service

    sudo systemctl daemon-reload
    sudo systemctl enable --now velutina-bot
    sudo systemctl status velutina-bot


## RoboFlow und Velu DEtect

Fotos lassen sich über spezialisierte KI-Webtools und Smartphone-Apps wie VeluDetect, HornetLog oder die velutina-App automatisch auf die Asiatische Hornisse (Vespa velutina) prüfen. Diese Dienste unterscheiden per Bilderkennung in wenigen Sekunden zwischen der invasiven Art, der heimischen Europäischen Hornisse und anderen Wespen.

### Einen Account erstellen

Unter https://app.roboflow.com/login geht das ganz einfach:

1. Anmeldeoption hier auswählen (anders oder wie hier "Continue with Email")
   Nach Eingabe deiber EMail-Adresse bekommst du einen Link zur Bestätigung geschickt.

2. In der empfdangene Email auf "Sign in to Roboflow" klicken.
3. Name eingeben und die Bedingungen akzeptieren.
4. Für den Workspace kann man einen beliebigen Namen verwenden. Auch der vorgeschlagene "Core-Plan" ist ausreichend.
5. Die nächsten Schritte kann man einfach mit "Skip" (unten links) überspringen.

### API Key finden und kopieren

Unter "Settings"->"API Keys" findet sich unter "Private API Key" ein APIKey, der für den Aurif benötigt wird.
Sollte dies noch nicht der Fall sein, dann kannst Du mit "Generate New Key" einen ApiKey geniereien und kopieren.

Den kopierten API-Key tragen wir in die Datei .env (in /home/velutina/velutina-bot) ein. 


## Meta Business und WhatsApp



## to be extended (mehr kommt noch)


## Releases

### 0.1     Initial Upload

