function doPost(e) {
    if (!e || !e.postData || !e.postData.contents) {
        return ContentService.createTextOutput("❌ Error: No se recibieron datos en la solicitud POST.")
            .setMimeType(ContentService.MimeType.TEXT);
    }

    try {
        var data = JSON.parse(e.postData.contents);
        var ss = SpreadsheetApp.getActiveSpreadsheet();

        // Ensure data is an array
        if (!Array.isArray(data)) {
            data = [data];
        }

        data.forEach((item, index) => {
            // Get or create sheet
            var sheet = ss.getSheetByName(item.sheet);
            var headers = Object.keys(item.data);
            if (!sheet) {
                sheet = ss.insertSheet(item.sheet);
                sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
            }
            // Get values in order of headers
            var rowData = headers.map(header => item.data[header] || '');
            sheet.appendRow(rowData);
        });

        return ContentService.createTextOutput("✅ Datos guardados correctamente.")
            .setMimeType(ContentService.MimeType.TEXT);
    } catch (error) {
        Logger.log("❌ Error procesando datos: " + error.toString());
        return ContentService.createTextOutput("❌ Error procesando datos: " + error)
            .setMimeType(ContentService.MimeType.TEXT);
    }
}

function doGet(e) {
    try {
        var sheetName = e && e.parameter && e.parameter.sheet ? e.parameter.sheet : "Resumen";
        var usernameFilter = e && e.parameter && e.parameter.username ? e.parameter.username : null;
        var ss = SpreadsheetApp.getActiveSpreadsheet();
        var sheet = ss.getSheetByName(sheetName);
        if (!sheet) {
            return ContentService.createTextOutput(`❌ Error: No se encontró la hoja '${sheetName}'.`)
                .setMimeType(ContentService.MimeType.TEXT);
        }

        var data = sheet.getDataRange().getValues();
        var headers = data.shift();
        var jsonData = data.map(row => {
            var obj = {};
            headers.forEach((header, index) => {
                obj[header] = row[index];
            });
            return obj;
        });

        // Filter by username if the parameter is provided
        if (usernameFilter) {
            jsonData = jsonData.filter(item => item.username && item.username === usernameFilter);
        }

        return ContentService.createTextOutput(JSON.stringify(jsonData))
            .setMimeType(ContentService.MimeType.JSON);
    } catch (error) {
        Logger.log("❌ Error procesando datos: " + error.toString());
        return ContentService.createTextOutput("❌ Error procesando datos: " + error)
            .setMimeType(ContentService.MimeType.TEXT);
    }
}

