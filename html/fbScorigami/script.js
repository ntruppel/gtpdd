const winScore = new Set();
const lossScore = new Set();
var textCaption;

import json from './json.js';
const parsedJSON = JSON.parse(json)
console.log(parsedJSON.updated);

const caption = document.querySelector("h3");
caption.innerHTML = "Data Last Updated: " + parsedJSON.updated;
var usages = parsedJSON.results;

// Add to the table
for (let i = 0; i <= 100; i++) {
winScore.add(i);
}
for (let i = 0; i <= 57; i++) {
lossScore.add(i);
}

// Create headers
const zeroPad = (num, places) => String(num).padStart(places, "0");
const theadTr = document.querySelector("thead tr");
for (const u of winScore) {
const th = document.createElement("th");
th.innerHTML = zeroPad(u, 2);
theadTr.appendChild(th);
}

// Create data rows
const tbody = document.querySelector("tbody");
for (const d of lossScore) {
const tr = document.createElement("tr");
const th = document.createElement("th");
th.innerHTML = zeroPad(d, 2);
th.style.backgroundColor = "lightgray";
tr.appendChild(th);

for (const u of winScore) {
    const td = document.createElement("td");
    const ud = usages.find((ud) => ud.winScore === u && ud.lossScore === d);

    if (ud) {
    td.innerHTML = ud.numGames;
    var backgroundColor = new String();
    var color = new String();
    let textCaption = u + " - " + d + " \n"
    let onlySwitch = new String();
        
    if (ud.numGames == 1){ onlySwitch = "Only"; }
    else {onlySwitch = "Last";}

    if (ud.lastWin) {
        if (ud.lastLoss) {
          backgroundColor = "midnightblue";
          color = "white";
          textCaption = textCaption + onlySwitch + " Tech Win: " + ud.lastWin + "\n" + onlySwitch +" Tech Loss: " + ud.lastLoss
        } else {
          backgroundColor = "dodgerblue";
          color = "white";
          textCaption = textCaption + onlySwitch + " Game: " + ud.lastWin
        }
      } else if (ud.lastLoss) {
        if (u == d) {
          backgroundColor = "midnightblue"
          color = "white";
          textCaption =  textCaption + onlySwitch + " Game: " + ud.lastLoss
        } else {
          backgroundColor = "firebrick";
          color = "white";
          textCaption =  textCaption + onlySwitch + " Game: " + ud.lastLoss
        }
      }
      td.style.backgroundColor = backgroundColor;
      td.style.color = color;
      td.id = textCaption;
      td.style.borderColor = "black";
    }
    if (
    d > u ||
    (d == 1 && u == 1) ||
    (d == 0 && u == 1) ||
    (d == 1 && u == 2) ||
    (d == 1 && u == 3) ||
    (d == 1 && u == 4) ||
    (d == 1 && u == 5) ||
    (d == 1 && u == 7)
    ) {
    td.style.backgroundColor = "black";
    }

    tr.appendChild(td);
}

tbody.appendChild(tr);
}
