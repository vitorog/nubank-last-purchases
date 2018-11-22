import request from 'request';
import GoogleSpreadsheet from 'google-spreadsheet';
import async from 'async';

// Figure out some way to discover the API?                   
const EVENTS_API = "https://prod-s0-webapp-proxy.nubank.com.br//api/proxy/AJxL5LBXpt2AE_Fgf6VhQySZjwN1QoLoxg.aHR0cHM6Ly9wcm9kLXMwLWZhY2FkZS5udWJhbmsuY29tLmJyL2FwaS9jdXN0b21lcnMvNTRmNzBkMmYtNWYwNS00YjQxLWIyMGEtMGQ2ZGNkYjYzOWVkL2ZlZWQ";
const TOKEN = process.argv[2];
const SPREADSHEET_ID = process.argv[3];
const CLIENT_SECRET_JSON = './client_secret.json';

const auth = `Bearer ${TOKEN}`;

var options = {
    url: EVENTS_API,
    headers: {
        'Authorization': auth
    }
};

const parseEvents = (events) => {
    console.log("Parsing events...");
    const today = new Date();
    return events
        .filter(event => event.category == "transaction")
        .map(element => {
            const date = new Date(Date.parse(element.time));
            return {
                description: element.description,
                amount: element.amount,
                category: 'Nubank',
                time: date,
                id: element.id
            }
        })
        .filter(p => p.time.getFullYear() == today.getFullYear())
        .sort((a, b) => a.time - b.time);
}

const formatDate = date => date.getDate() + "-" + (date.getMonth() + 1) + "-" + date.getFullYear();

const addPurchasesToSpreadsheet = purchases => {
    console.log("Adding purchases to spreadsheet...");
    // spreadsheet key is the long id in the sheets URL
    const doc = new GoogleSpreadsheet(SPREADSHEET_ID);
    var sheet;

    async.series([
        function setAuth(step) {
            console.log("Authenticating...");
            // see notes below for authentication instructions!
            var creds = require(CLIENT_SECRET_JSON);
            doc.useServiceAccountAuth(creds, step);
        },
        function getInfoAndWorksheets(step) {
            console.log("Opening spreadsheet...");
            doc.getInfo(function (err, info) {
                console.log('Loaded doc: ' + info.title + ' by ' + info.author.email);
                sheet = info.worksheets[0];
                console.log('sheet 1: ' + sheet.title + ' ' + sheet.rowCount + 'x' + sheet.colCount);
                step();
            });
        },
        function updateCells(step) {
            console.log("Updating cells...");
            const endIndex = purchases.length + 1;
            sheet.getCells({
                'min-row': 2,
                'max-row': endIndex,
                'max-col': 5,
                'return-empty': true
            }, function (err, cells) {
                var offset = 0;
                purchases.forEach(p => {
                    cells[offset].value = p.description;
                    cells[offset + 1].value = `=${p.amount}/100`;
                    cells[offset + 2].value = p.category;
                    cells[offset + 3].value = formatDate(p.time);
                    cells[offset + 4].value = p.id;
                    offset += 5;
                })
                sheet.bulkUpdateCells(cells); //async
                step();
            });
        }
    ]);
}

request(options, (error, response, body) => {
    console.log(response.statusCode);
    if (response.statusCode === 200) {
        const events = JSON.parse(body).events;
        const purchases = parseEvents(events);
        addPurchasesToSpreadsheet(purchases);
    }else{
        console.log("Failed to read Nubank purchases.");
    }
});