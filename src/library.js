function doPost(e) {
    if (!e || !e.postData || !e.postData.contents) {
        return ContentService.createTextOutput("❌ Error: No se recibieron datos en la solicitud POST.")
            .setMimeType(ContentService.MimeType.TEXT);
    }

    try {
        var payload = JSON.parse(e.postData.contents);
        var ss = SpreadsheetApp.getActiveSpreadsheet();
        var sheetName = payload.sheet;
        var data = payload.data;

        // Get or create sheet
        var sheet = ss.getSheetByName(sheetName);
        if (!sheet) {
            sheet = ss.insertSheet(sheetName);
            // Create headers based on data keys
            var headers = Object.keys(data);
            sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
        }

        // Get values in order of headers
        var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
        var rowData = headers.map(header => data[header] || '');

        // Append data
        sheet.appendRow(rowData);

        return ContentService.createTextOutput("✅ Datos guardados correctamente.")
            .setMimeType(ContentService.MimeType.TEXT);
    } catch (error) {
        Logger.log("❌ Error procesando datos: " + error.toString());
        return ContentService.createTextOutput("❌ Error procesando datos: " + error)
            .setMimeType(ContentService.MimeType.TEXT);
    }
}
