/**
 * Google Apps Script to receive temperature data from Raspberry Pi Pico W
 * and log it to a Google Sheet
 */

// Spreadsheet ID - replace with your actual spreadsheet ID
const SPREADSHEET_ID = 'your_spreadsheet_id';
const SHEET_NAME = 'Temperature Data';

/**
 * Process POST requests from the Pico W
 */
function doPost(e) {
  try {
    // Log the incoming request for debugging
    console.log("Received POST request");
    console.log("Content type: " + e.contentType);
    console.log("Post data: " + JSON.stringify(e.postData));
    
    // Parse the incoming JSON data
    const jsonData = JSON.parse(e.postData.contents);
    console.log("Parsed data: " + JSON.stringify(jsonData));
    
    const rawAdc = jsonData.raw_adc;
    const deviceId = jsonData.device_id || "unknown_device";
    
    // Get current timestamp
    const timestamp = new Date();
    
    // Calculate temperature from raw ADC value
    // Formula from RP2040 datasheet
    const voltage = (3.3 / 65535) * rawAdc;
    const temperature = 27 - (voltage - 0.706) / 0.001721;
    const tempRounded = Math.round(temperature * 10) / 10; // Round to 1 decimal place
    
    // Log data to spreadsheet
    logData(timestamp, deviceId, rawAdc, voltage, tempRounded);
    
    // Return success response
    return ContentService.createTextOutput(JSON.stringify({
      'status': 'success',
      'timestamp': timestamp.toISOString(),
      'temperature': tempRounded
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    // Log the error
    console.error("Error processing request: " + error);
    console.error("Stack: " + error.stack);
    
    // Return error response
    return ContentService.createTextOutput(JSON.stringify({
      'status': 'error',
      'message': error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Process GET requests (for testing the deployment)
 */
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    'status': 'success',
    'message': 'Google Apps Script is running correctly. Use POST to send data.',
    'timestamp': new Date().toISOString()
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Log data to the spreadsheet
 */
function logData(timestamp, deviceId, rawAdc, voltage, temperature) {
  try {
    // Open the spreadsheet
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    
    // Get or create the sheet
    let sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      
      // Add headers if this is a new sheet
      sheet.appendRow([
        'Timestamp', 
        'Device ID', 
        'Raw ADC Value', 
        'Voltage (V)', 
        'Temperature (°C)'
      ]);
      
      // Format headers
      sheet.getRange(1, 1, 1, 5).setFontWeight('bold');
      
      // Set column widths
      sheet.setColumnWidth(1, 180); // Timestamp
      sheet.setColumnWidth(2, 100); // Device ID
      sheet.setColumnWidth(3, 120); // Raw ADC
      sheet.setColumnWidth(4, 100); // Voltage
      sheet.setColumnWidth(5, 120); // Temperature
    }
    
    // Format timestamp
    const formattedTimestamp = Utilities.formatDate(
      timestamp, 
      Session.getScriptTimeZone(), 
      'yyyy-MM-dd HH:mm:ss'
    );
    
    // Append data row
    sheet.appendRow([
      formattedTimestamp,
      deviceId,
      rawAdc,
      voltage.toFixed(3),
      temperature.toFixed(1)
    ]);
    
    console.log("Data logged successfully to spreadsheet");
    return true;
  } catch (error) {
    console.error("Error logging data: " + error);
    return false;
  }
}

/**
 * Setup function to create a deployment
 * Run this function once to set up the web app
 */
function setupWebApp() {
  // Log the web app URL
  const url = ScriptApp.getService().getUrl();
  console.log('Deploy this web app and use this URL in your Pico W code:');
  console.log(url);
  
  // Test if the spreadsheet ID is valid
  testSpreadsheetConnection();
}

/**
 * Test function to verify the spreadsheet connection
 */
function testSpreadsheetConnection() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheets = ss.getSheets().map(sheet => sheet.getName());
    console.log('Successfully connected to spreadsheet!');
    console.log('Available sheets:', sheets);
    return 'Success';
  } catch (error) {
    console.error('Error connecting to spreadsheet:', error);
    return 'Error: ' + error;
  }
}

/**
 * Manual test function to simulate receiving data from Pico W
 * Run this function to test the script without a physical Pico W
 */
function testWithSampleData() {
  // Create a mock event object
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        raw_adc: 28756,
        device_id: "test_device"
      })
    },
    contentType: "application/json"
  };
  
  // Process the mock event
  const result = doPost(mockEvent);
  console.log("Test result: " + result.getContent());
  return "Test completed";
}
