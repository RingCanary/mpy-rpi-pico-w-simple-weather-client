/**
 * Google Apps Script to receive environmental data from ESP32-C6 and Pico W
 * and log it to a Google Sheet
 */

// Configuration: Spreadsheet ID is read from Script Properties for safety.
// Set once in the editor console:
//   PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', 'YOUR_SHEET_ID')
const SPREADSHEET_ID = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
const SHEET_NAME = 'Environmental Data';
const PICO_SHEET_NAME = 'PICOMON';

// Cache for deduplication (stores recent requests to prevent duplicates)
const cache = CacheService.getScriptCache();
const DEDUP_WINDOW_SECONDS = 10; // Ignore duplicate requests within 10 seconds

/**
 * Process POST requests from both ESP32-C6 and Pico W
 */
function doPost(e) {
  try {
    // Enhanced logging for debugging
    console.log('=== POST Request Received ===');
    console.log('Timestamp:', new Date().toISOString());
    console.log('Content Type:', e.contentType);
    console.log('Content Length:', e.postData ? e.postData.length : 'N/A');
    console.log('Parameters:', JSON.stringify(e.parameter));
    console.log('Query String:', e.queryString);
    
    if (!e || !e.postData || !e.postData.contents) {
      console.error('Empty request body');
      return _json({ status: 'error', message: 'Empty body' });
    }
    
    console.log('Raw POST data:', e.postData.contents.substring(0, 500)); // Log first 500 chars
    
    if (e.contentType && e.contentType.indexOf('application/json') === -1) {
      console.warn('Unexpected content type:', e.contentType);
    }

    if (!SPREADSHEET_ID) {
      return _json({ status: 'error', message: 'SPREADSHEET_ID not configured in Script Properties' });
    }

    // Parse the incoming JSON data
    const jsonData = JSON.parse(e.postData.contents);
    console.log('Parsed data:', JSON.stringify(jsonData));
    
    // Determine device type based on device_id or data structure
    const isPicoW = jsonData.device_id && jsonData.device_id.includes('pico_w');
    
    if (isPicoW) {
      // Handle Pico W data
      return handlePicoData(jsonData, e);
    }

    const safeNum = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };

    const payload = {
      temperature: safeNum(jsonData.temperature),
      humidity: safeNum(jsonData.humidity),
      pressure: safeNum(jsonData.pressure),
      gas: safeNum(jsonData.gas),
      device_id: jsonData.device_id || 'unknown_device',
      device_ts: jsonData.device_ts || null,
      firmware: jsonData.firmware || null,
      request_id: jsonData.request_id || null,
      // SMELLY GAS tracking metrics
      stink_count: jsonData.stink_count || 0,
      redirect_count: jsonData.redirect_count || 0,
      success_count: jsonData.success_count || 0,
      total_requests: jsonData.total_requests || 0,
      uptime_cycles: jsonData.uptime_cycles || 0,
      reset_count: jsonData.reset_count || 0,
    };

    // Create deduplication key - prefer request_id if available, otherwise use data combination
    const dedupKey = payload.request_id || 
      `${payload.device_id}_${payload.device_ts}_${payload.temperature}_${payload.humidity}`;
    
    // Check if we've seen this exact data recently
    const cachedRequest = cache.get(dedupKey);
    if (cachedRequest) {
      console.log('Duplicate request detected, skipping data logging. Key:', dedupKey);
      return _json({
        status: 'success',
        message: 'Duplicate request (data already processed)',
        cached: true,
        timestamp: new Date().toISOString(),
      });
    }
    
    // Store in cache to prevent duplicates
    cache.put(dedupKey, 'processed', DEDUP_WINDOW_SECONDS);

    const timestamp = new Date();

    // Log data to spreadsheet
    logData(timestamp, payload);
    console.log('New data logged successfully. Key:', dedupKey);

    return _json({
      status: 'success',
      timestamp: timestamp.toISOString(),
      ...payload,
    });
  } catch (error) {
    console.error('Error processing request:', error, error && error.stack);
    return _json({ status: 'error', message: String(error) });
  }
}

/**
 * Process GET requests (for testing the deployment)
 */
function doGet(e) {
  // Enhanced GET endpoint for debugging
  const debugInfo = {
    status: 'success',
    message: 'Google Apps Script is running correctly. Use POST to send data.',
    timestamp: new Date().toISOString(),
    debug: {
      spreadsheetConfigured: !!SPREADSHEET_ID,
      scriptTimeZone: Session.getScriptTimeZone(),
      executionApi: 'Web App',
      cacheAvailable: !!cache,
      dedupWindowSeconds: DEDUP_WINDOW_SECONDS,
      sheets: {
        esp32: SHEET_NAME,
        picoW: PICO_SHEET_NAME
      }
    },
    deployment: {
      url: ScriptApp.getService().getUrl(),
      projectKey: ScriptApp.getProjectKey(),
    },
    devices: {
      esp32: 'Logs to Environmental Data sheet',
      picoW: 'Logs to PICOMON sheet (device_id must contain "pico_w")'
    }
  };
  
  console.log('GET request received:', JSON.stringify(debugInfo));
  return _json(debugInfo);
}

/**
 * Log data to the spreadsheet
 */
function logData(timestamp, payload) {
  const { 
    device_id, temperature, humidity, pressure, gas, device_ts, firmware,
    stink_count, redirect_count, success_count, total_requests, uptime_cycles, reset_count
  } = payload;
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

    let sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow([
        'Timestamp',
        'Device ID',
        'Temperature (°C)',
        'Humidity (%)',
        'Pressure (hPa)',
        'Gas Resistance (kOhms)',
        'Device Timestamp',
        'Firmware',
        'STINK Count',
        'Redirect Count',
        'Success Count', 
        'Total Requests',
        'Uptime Cycles',
        'Reset Count',
      ]);
      sheet.getRange(1, 1, 1, 14).setFontWeight('bold');
      sheet.setColumnWidth(1, 180);
      sheet.setColumnWidth(2, 120);
      sheet.setColumnWidth(3, 140);
      sheet.setColumnWidth(4, 140);
      sheet.setColumnWidth(5, 140);
      sheet.setColumnWidth(6, 180);
      sheet.setColumnWidth(7, 180);
      sheet.setColumnWidth(8, 140);
    }

    const formattedTimestamp = Utilities.formatDate(
      timestamp,
      Session.getScriptTimeZone(),
      'yyyy-MM-dd HH:mm:ss'
    );

    const toFixedOrBlank = (n) => (Number.isFinite(n) ? n.toFixed(2) : '');

    sheet.appendRow([
      formattedTimestamp,
      device_id,
      toFixedOrBlank(temperature),
      toFixedOrBlank(humidity),
      toFixedOrBlank(pressure),
      toFixedOrBlank(gas),
      device_ts || '',
      firmware || '',
      stink_count || 0,
      redirect_count || 0,
      success_count || 0,
      total_requests || 0,
      uptime_cycles || 0,
      reset_count || 0,
    ]);

    console.log('Data logged successfully to spreadsheet');
    return true;
  } catch (error) {
    console.error('Error logging data:', error);
    return false;
  }
}

/** Utility to return JSON responses */
function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * Setup function to create a deployment
 * Run this function once to set up the web app
 */
function setupWebApp() {
  const url = ScriptApp.getService().getUrl();
  console.log('Deploy this web app and use this URL in your ESP32-C6 code:');
  console.log(url);
  testSpreadsheetConnection();
}

/**
 * Test function to verify the spreadsheet connection
 */
function testSpreadsheetConnection() {
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheets = ss.getSheets().map((sheet) => sheet.getName());
    console.log('Successfully connected to spreadsheet!');
    console.log('Available sheets:', sheets);
    return 'Success';
  } catch (error) {
    console.error('Error connecting to spreadsheet:', error);
    return 'Error: ' + error;
  }
}

/**
 * Handle Pico W data
 */
function handlePicoData(jsonData, e) {
  try {
    const safeNum = (v) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };

    const payload = {
      device_id: jsonData.device_id || 'pico_w_unknown',
      raw_adc: safeNum(jsonData.raw_adc),
      voltage: safeNum(jsonData.voltage),
      temperature: safeNum(jsonData.temperature),
      device_ts: jsonData.device_ts || null,
      firmware: jsonData.firmware || null,
      request_id: jsonData.request_id || null,
      // SMELLY GAS tracking metrics
      stink_count: jsonData.stink_count || 0,
      redirect_count: jsonData.redirect_count || 0,
      success_count: jsonData.success_count || 0,
      total_requests: jsonData.total_requests || 0,
      uptime_cycles: jsonData.uptime_cycles || 0,
      reset_count: jsonData.reset_count || 0,
    };

    // Create deduplication key
    const dedupKey = payload.request_id || 
      `${payload.device_id}_${payload.device_ts}_${payload.temperature}`;
    
    // Check cache for duplicates
    const cachedRequest = cache.get(dedupKey);
    if (cachedRequest) {
      console.log('Duplicate Pico request detected, skipping. Key:', dedupKey);
      return _json({
        status: 'success',
        message: 'Duplicate request (data already processed)',
        cached: true,
        timestamp: new Date().toISOString(),
        temperature: payload.temperature,
      });
    }
    
    // Store in cache
    cache.put(dedupKey, 'processed', DEDUP_WINDOW_SECONDS);
    
    const timestamp = new Date();
    
    // Log Pico data
    logPicoData(timestamp, payload);
    console.log('New Pico data logged successfully. Key:', dedupKey);
    
    return _json({
      status: 'success',
      timestamp: timestamp.toISOString(),
      temperature: payload.temperature,
      ...payload,
    });
  } catch (error) {
    console.error('Error processing Pico request:', error);
    return _json({ status: 'error', message: String(error) });
  }
}

/**
 * Log Pico W data to PICOMON sheet
 */
function logPicoData(timestamp, payload) {
  const { 
    device_id, raw_adc, voltage, temperature, device_ts, firmware,
    stink_count, redirect_count, success_count, total_requests, uptime_cycles, reset_count
  } = payload;
  
  try {
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    
    let sheet = ss.getSheetByName(PICO_SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(PICO_SHEET_NAME);
      sheet.appendRow([
        'Timestamp',
        'Device ID',
        'Core Temp (°C)',
        'Raw ADC',
        'Voltage (V)',
        'Device Timestamp',
        'Firmware',
        'STINK Count',
        'Redirect Count',
        'Success Count', 
        'Total Requests',
        'Uptime Cycles',
        'Reset Count',
      ]);
      sheet.getRange(1, 1, 1, 13).setFontWeight('bold');
      
      // Set column widths
      sheet.setColumnWidth(1, 180); // Timestamp
      sheet.setColumnWidth(2, 100); // Device ID
      sheet.setColumnWidth(3, 120); // Core Temp
      sheet.setColumnWidth(4, 100); // Raw ADC
      sheet.setColumnWidth(5, 100); // Voltage
      sheet.setColumnWidth(6, 180); // Device Timestamp
      sheet.setColumnWidth(7, 140); // Firmware
    }
    
    const formattedTimestamp = Utilities.formatDate(
      timestamp,
      Session.getScriptTimeZone(),
      'yyyy-MM-dd HH:mm:ss'
    );
    
    const toFixedOrBlank = (n, decimals = 2) => (Number.isFinite(n) ? n.toFixed(decimals) : '');
    
    sheet.appendRow([
      formattedTimestamp,
      device_id,
      toFixedOrBlank(temperature),
      raw_adc || '',
      toFixedOrBlank(voltage, 3),
      device_ts || '',
      firmware || '',
      stink_count || 0,
      redirect_count || 0,
      success_count || 0,
      total_requests || 0,
      uptime_cycles || 0,
      reset_count || 0,
    ]);
    
    console.log('Pico data logged successfully to PICOMON sheet');
    return true;
  } catch (error) {
    console.error('Error logging Pico data:', error);
    return false;
  }
}

/**
 * Manual test function to simulate receiving data from ESP32-C6
 * Run this function to test the script without a physical device
 */
function testWithSampleData() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        temperature: 32.58,
        humidity: 30.39,
        pressure: 968.03,
        gas: 3.8,
        device_id: 'test_data',
        device_ts: new Date().toISOString(),
        firmware: 'test-0.0.1',
      }),
    },
    contentType: 'application/json',
  };
  const result = doPost(mockEvent);
  console.log('Test result: ' + result.getContent());
  return 'Test completed';
}

/**
 * Manual test function for Pico W
 */
function testWithSamplePicoData() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        device_id: 'pico_w_test',
        raw_adc: 27500,
        voltage: 1.385,
        temperature: 35.2,
        device_ts: new Date().getTime() / 1000,
        firmware: 'test-1.0',
        request_id: 'pico_test_' + new Date().getTime(),
        stink_count: 5,
        redirect_count: 2,
        success_count: 10,
        total_requests: 17,
        uptime_cycles: 15,
        reset_count: 0,
      }),
    },
    contentType: 'application/json',
  };
  const result = doPost(mockEvent);
  console.log('Pico test result: ' + result.getContent());
  return 'Pico test completed';
}

/**
 * Manual test function for daily archiving
 * Test the archive functionality without waiting for the scheduled trigger
 */
function testDailyArchive() {
  console.log('=== Testing Daily Archive Function ===');
  try {
    archiveDailyData();
    console.log('Archive test completed successfully');
    return 'Archive test completed';
  } catch (error) {
    console.error('Archive test failed:', error);
    return 'Archive test failed: ' + error.message;
  }
}

/**
 * Debug function to inspect current data in sheets
 * Run this to understand what data exists before archiving
 */
function debugSheetData() {
  console.log('=== Debugging Sheet Data ===');

  if (!SPREADSHEET_ID) {
    console.error('SPREADSHEET_ID not configured');
    return 'SPREADSHEET_ID not configured';
  }

  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  const now = new Date();
  const today = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const yesterdayStr = Utilities.formatDate(yesterday, Session.getScriptTimeZone(), 'yyyy-MM-dd');

  console.log(`Today: ${today}`);
  console.log(`Yesterday: ${yesterdayStr}`);
  console.log(`Script Timezone: ${Session.getScriptTimeZone()}`);

  const sheetsToCheck = [
    { name: SHEET_NAME, label: 'Environmental Data' },
    { name: PICO_SHEET_NAME, label: 'PICOMON' },
  ];

  sheetsToCheck.forEach(({ name, label }) => {
    console.log(`\n--- ${label} (${name}) ---`);
    const sheet = ss.getSheetByName(name);
    if (!sheet) {
      console.log(`Sheet not found`);
      return;
    }

    const lastRow = sheet.getLastRow();
    console.log(`Last row: ${lastRow}`);

    if (lastRow <= 1) {
      console.log('No data rows (only header or empty)');
      return;
    }

    // Get first 10 rows of data for inspection
    const dataRows = Math.min(10, lastRow - 1);
    const dataRange = sheet.getRange(2, 1, dataRows, sheet.getLastColumn());
    const data = dataRange.getValues();

    console.log(`Sample data (first ${dataRows} rows):`);
    data.forEach((row, index) => {
      const timestamp = String(row[0]);
      const datePart = timestamp.substring(0, 10);
      const isToday = datePart === today;
      const isYesterday = datePart === yesterdayStr;

      console.log(`Row ${index + 2}: "${timestamp}" -> Date: "${datePart}" | Today: ${isToday} | Yesterday: ${isYesterday}`);
    });

    // Count rows by date
    const allDataRange = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn());
    const allData = allDataRange.getValues();

    const dateCounts = {};
    allData.forEach((row) => {
      const timestamp = String(row[0]);
      const datePart = timestamp.substring(0, 10);
      dateCounts[datePart] = (dateCounts[datePart] || 0) + 1;
    });

    console.log(`Row counts by date:`);
    Object.entries(dateCounts).forEach(([date, count]) => {
      console.log(`  ${date}: ${count} rows`);
    });
  });

  return 'Debug completed - check logs for details';
}


/**
 * Get archive status and statistics
 */
function getArchiveStatus() {
  const state = _getArchiveState();
  const status = {
    lastArchiveDate: state.lastArchiveDate || 'Never',
    lastArchiveTime: state.lastArchiveTime || 'Never',
    totalArchivedRows: state.totalArchivedRows || 0,
    spreadsheetId: SPREADSHEET_ID ? 'Configured' : 'Not configured',
    sheets: ['Environmental Data', 'PICOMON'],
    nextScheduledArchive: '1:00 AM daily',
  };

  console.log('Archive Status:', JSON.stringify(status, null, 2));
  return status;
}


/**
 * ========== Monitoring and Slack Alerts ==========
 * Monitors two sheets for new rows and sends Slack alerts if stalled.
 */
const INACTIVITY_MINUTES = 5; // minutes without new rows before alerting
const ALERT_COOLDOWN_MINUTES = 30; // do not repeat alerts more frequently than this per sheet
const HVAC_TEMP_THRESHOLD = 25; // °C threshold for HVAC failure
const HVAC_ALERT_COOLDOWN_MINUTES = 30; // cooldown for HVAC alert
const STATE_PROPERTY_KEY = 'ALERT_STATE';
const SLACK_WEBHOOK = PropertiesService.getScriptProperties().getProperty('SLACK_WEBHOOK');
// const SHEET_NAME_TEST = 'Environmental Data Test';
// const PICO_SHEET_NAME_TEST = 'PICOMON Test';
/**
 * Main scheduled function: checks both sheets and alerts if needed
 * - Stale data alerts for Environmental Data and PICOMON
 * - HVAC temperature alert (Environmental Data column C)
 */
function slackAlert() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) {
    console.warn('slackAlert: could not acquire lock; skipping run');
    return;
  }

  try {
    if (!SPREADSHEET_ID) {
      console.error('slackAlert: SPREADSHEET_ID not configured');
      return;
    }

    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const now = new Date();
    const nowIso = now.toISOString();

    const sheetsToCheck = [
      { name: SHEET_NAME, label: 'Environmental Data' },
      { name: PICO_SHEET_NAME, label: 'PICOMON' },
    ];

    const state = _getAlertState();
    const alerts = [];

    sheetsToCheck.forEach(({ name, label }) => {
      const sheet = ss.getSheetByName(name);
      const currentLastRow = sheet ? sheet.getLastRow() : 0;

      if (!state[name]) {
        state[name] = {
          lastObservedRow: currentLastRow,
          lastChangeAt: nowIso,
          lastAlertAt: null,
        };
        console.log(`Initialized monitoring state for ${label}: row=${currentLastRow}`);
        return; // no alert on first observation
      }

      const sheetState = state[name];

      if (currentLastRow > (sheetState.lastObservedRow || 0)) {
        // New data arrived; reset timers
        sheetState.lastObservedRow = currentLastRow;
        sheetState.lastChangeAt = nowIso;
        sheetState.lastAlertAt = null; // clear cooldown on recovery
        console.log(`Activity resumed on ${label}; lastRow=${currentLastRow}`);
        return;
      }

      const lastChangeAt = new Date(sheetState.lastChangeAt || nowIso);
      const minutesStalled = Math.floor((now.getTime() - lastChangeAt.getTime()) / 60000);

      if (minutesStalled >= INACTIVITY_MINUTES) {
        const lastAlertAt = sheetState.lastAlertAt ? new Date(sheetState.lastAlertAt) : null;
        const minutesSinceLastAlert = lastAlertAt
          ? Math.floor((now.getTime() - lastAlertAt.getTime()) / 60000)
          : null;

        const cooldownOk = lastAlertAt === null || minutesSinceLastAlert >= ALERT_COOLDOWN_MINUTES;
        if (cooldownOk) {
          // Queue alert and set lastAlertAt
          alerts.push({ label, currentLastRow, minutesStalled });
          sheetState.lastAlertAt = nowIso;
        } else {
          console.log(`Cooldown active for ${label}; last alert ${minutesSinceLastAlert} min ago`);
        }
      } else {
        console.log(`${label} inactive for ${minutesStalled} min (< ${INACTIVITY_MINUTES}); no alert`);
      }
    });

    // HVAC temperature alert check (Environmental Data latest row, column C)
    try {
      const hvacState = state[SHEET_NAME] || (state[SHEET_NAME] = { lastObservedRow: 0, lastChangeAt: new Date().toISOString(), lastAlertAt: null, lastHvacAlertAt: null });
      const ssEnv = ss.getSheetByName(SHEET_NAME);
      if (ssEnv) {
        const lastRow = ssEnv.getLastRow();
        if (lastRow > 1) { // ensure there is at least one data row beyond header
          const rowValues = ssEnv.getRange(lastRow, 1, 1, 8).getValues()[0];
          const ts = rowValues[0]; // Column A Timestamp (string)
          const tempStr = rowValues[2]; // Column C Temperature (string like '25.30')
          const temp = typeof tempStr === 'number' ? tempStr : parseFloat(String(tempStr).replace(',', '.'));
          if (Number.isFinite(temp) && temp > HVAC_TEMP_THRESHOLD) {
            const lastHvacAlertAt = hvacState.lastHvacAlertAt ? new Date(hvacState.lastHvacAlertAt) : null;
            const now = new Date();
            const minutesSinceHvacAlert = lastHvacAlertAt ? Math.floor((now.getTime() - lastHvacAlertAt.getTime()) / 60000) : null;
            const cooldownOk = lastHvacAlertAt === null || minutesSinceHvacAlert >= HVAC_ALERT_COOLDOWN_MINUTES;
            if (cooldownOk) {
              const sheetUrl = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}`;
              const msg = `:thermometer: HVAC failure alert: Temperature ${temp.toFixed(2)}°C at ${ts} on Environmental Data (row ${lastRow}).\nSheet: ${sheetUrl}`;
              _postToSlack(msg);
              hvacState.lastHvacAlertAt = new Date().toISOString();
              console.log('HVAC alert sent:', msg);
            } else {
              console.log(`HVAC alert suppressed due to cooldown (${minutesSinceHvacAlert} min since last).`);
            }
          }
        }
      }
    } catch (e) {
      console.error('HVAC alert check failed:', e);
    }

    // Persist state regardless of alerts
    _setAlertState(state);

    if (alerts.length > 0) {
      const sheetUrl = `https://docs.google.com/spreadsheets/d/${SPREADSHEET_ID}`;
      const header = ':rotating_light: Power cut suspected: data stalled';
      const lines = alerts.map(a =>
        `• ${a.label}: no new rows for ${a.minutesStalled} min (lastRow=${a.currentLastRow})`
      );
      const message = `${header}\n${lines.join('\n')}\nSheet: ${sheetUrl}`;
      _postToSlack(message);
      console.log('Slack alert sent:', message);
    } else {
      console.log('No alerts to send this run');
    }
  } catch (err) {
    console.error('slackAlert error:', err, err && err.stack);
  } finally {
    try { lock.releaseLock(); } catch (e) {}
  }
}

/**
 * Read alert state from Script Properties
 */
function _getAlertState() {
  try {
    const raw = PropertiesService.getScriptProperties().getProperty(STATE_PROPERTY_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    console.error('Failed parsing alert state; resetting. Error:', e);
    return {};
  }
}

/**
 * Write alert state to Script Properties
 */
function _setAlertState(state) {
  PropertiesService.getScriptProperties().setProperty(STATE_PROPERTY_KEY, JSON.stringify(state));
}

/**
 * Post message to Slack via incoming webhook
 */
function _postToSlack(text) {
  if (!SLACK_WEBHOOK) {
    console.error('SLACK_WEBHOOK not set in Script Properties; cannot send Slack alert');
    return;
  }
  const payload = { text };
  const params = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };
  try {
    const resp = UrlFetchApp.fetch(SLACK_WEBHOOK, params);
    const code = resp.getResponseCode();
    if (code < 200 || code >= 300) {
      console.error('Slack webhook responded with non-2xx:', code, resp.getContentText());
    }
  } catch (e) {
    console.error('Slack webhook error:', e);
  }
}

/**
 * Create a minute-based time trigger for slackAlert()
 * Run once manually from the editor.
 */
function setupTriggers() {
  const existing = ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'slackAlert');
  existing.forEach(t => ScriptApp.deleteTrigger(t)); // ensure single trigger
  ScriptApp.newTrigger('slackAlert').timeBased().everyMinutes(1).create();
  console.log('Created time-driven trigger: slackAlert every 1 minute');
}

/**
 * Remove all triggers for slackAlert()
 */
function removeTriggers() {
  const existing = ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'slackAlert' || t.getHandlerFunction() === 'hourlyWeatherReport' || t.getHandlerFunction() === 'archiveDailyData');
  existing.forEach(t => ScriptApp.deleteTrigger(t));
  console.log(`Removed ${existing.length} trigger(s) for alerts/reports`);
}

/**
 * Create hourly trigger for weather reports
 */
function setupHourlyTrigger() {
  // ensure only one hourly trigger exists
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'hourlyWeatherReport')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('hourlyWeatherReport').timeBased().everyHours(1).create();
  console.log('Created time-driven trigger: hourlyWeatherReport every 1 hour');
}

/**
 * Send a weather report with the latest row from Environmental Data
 */
function hourlyWeatherReport() {
  try {
    if (!SPREADSHEET_ID) {
      console.error('hourlyWeatherReport: SPREADSHEET_ID not configured');
      return;
    }
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      console.warn('hourlyWeatherReport: Environmental Data sheet not found');
      return;
    }
    const lastRow = sheet.getLastRow();
    if (lastRow <= 1) {
      console.log('hourlyWeatherReport: no data rows');
      return;
    }
    const row = sheet.getRange(lastRow, 1, 1, 8).getValues()[0];
    const ts = row[0];
    const deviceId = row[1];
    const temp = row[2];
    const humidity = row[3];
    const pressure = row[4];
    const gas = row[5];
    const msg = `:sun_small_cloud: Weather report (Environmental Data)\n• Time: ${ts}\n• Device: ${deviceId}\n• Temp: ${temp}°C\n• Humidity: ${humidity}%\n• Pressure: ${pressure} hPa\n• Gas: ${gas} kOhms`;
    _postToSlack(msg);
    console.log('Hourly weather report sent:', msg);
  } catch (e) {
    console.error('hourlyWeatherReport error:', e);
  }
}

/**
 * ========== Daily Data Archiving ==========
 * Archives yesterday's data to date-specific sheets and keeps current day's data in active sheets
 */
const ARCHIVE_STATE_KEY = 'DAILY_ARCHIVE_STATE';
const ARCHIVE_LOCK_TIMEOUT = 60000; // 60 seconds lock timeout

/**
 * Main archive function - called by daily trigger
 * Archives yesterday's data and keeps only current day's data in active sheets
 */
function archiveDailyData() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(ARCHIVE_LOCK_TIMEOUT)) {
    console.warn('archiveDailyData: could not acquire lock; skipping run');
    return;
  }

  try {
    console.log('=== Starting daily data archive ===');

    if (!SPREADSHEET_ID) {
      console.error('archiveDailyData: SPREADSHEET_ID not configured');
      return;
    }

    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    const now = new Date();
    const today = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd');

    // Check if we already archived today's data
    const archiveState = _getArchiveState();
    if (archiveState.lastArchiveDate === today) {
      console.log(`Archive already completed for ${today}, skipping`);
      return;
    }

    const sheetsToArchive = [
      { name: SHEET_NAME, label: 'Environmental Data', columnCount: 14 },
      { name: PICO_SHEET_NAME, label: 'PICOMON', columnCount: 13 },
    ];

    let totalArchived = 0;
    let errors = [];

    sheetsToArchive.forEach(({ name, label, columnCount }) => {
      try {
        console.log(`Processing ${label} sheet...`);
        const sheet = ss.getSheetByName(name);
        if (!sheet) {
          console.warn(`Sheet ${name} not found, skipping`);
          return;
        }

        // Get yesterday's date in sheet timezone
        const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
        const yesterdayStr = Utilities.formatDate(yesterday, Session.getScriptTimeZone(), 'yyyy-MM-dd');

        // Archive yesterday's data
        const archivedCount = moveYesterdayData(sheet, yesterdayStr, columnCount);
        if (archivedCount > 0) {
          totalArchived += archivedCount;
          console.log(`Archived ${archivedCount} rows from ${label}`);
        }

        // Clean current sheet to keep only today's data
        const cleanedCount = cleanCurrentDayData(sheet, today);
        if (cleanedCount > 0) {
          console.log(`Cleaned ${cleanedCount} old rows from ${label}`);
        }

      } catch (error) {
        const errorMsg = `Error processing ${label}: ${error.message}`;
        console.error(errorMsg);
        errors.push(errorMsg);
      }
    });

    // Update archive state
    archiveState.lastArchiveDate = today;
    archiveState.lastArchiveTime = now.toISOString();
    archiveState.totalArchivedRows = (archiveState.totalArchivedRows || 0) + totalArchived;
    _setArchiveState(archiveState);

    const summary = `Archive completed: ${totalArchived} rows archived, ${errors.length} errors`;
    console.log(`=== ${summary} ===`);

    if (errors.length > 0 && SLACK_WEBHOOK) {
      const errorMsg = `:warning: Archive errors occurred:\n${errors.join('\n')}`;
      _postToSlack(errorMsg);
    }

  } catch (error) {
    console.error('archiveDailyData failed:', error, error && error.stack);
    if (SLACK_WEBHOOK) {
      _postToSlack(`:exclamation: Archive failed: ${error.message}`);
    }
  } finally {
    try { lock.releaseLock(); } catch (e) {}
  }
}

/**
 * Fast-extract date key (yyyy-MM-dd) from a timestamp cell value.
 * Avoids expensive Utilities.formatDate when the cell already contains
 * our standard string format 'yyyy-MM-dd HH:mm:ss'. Falls back to
 * Utilities.formatDate only when needed.
 */
function _dateKeyFromCell(value, tz) {
  // Fast path: our logger writes timestamps as strings 'yyyy-MM-dd HH:mm:ss'
  if (typeof value === 'string') {
    // If it looks like ISO-like date at the start, slice the date portion
    if (value.length >= 10 && value.charAt(4) === '-' && value.charAt(7) === '-') {
      return value.substring(0, 10);
    }
    // If it's some other string, try Date parsing as fallback
    const d = new Date(value);
    if (!isNaN(d.getTime())) {
      return Utilities.formatDate(d, tz, 'yyyy-MM-dd');
    }
    return null;
  }

  // If it's a Date object
  if (value && typeof value === 'object' && value instanceof Date) {
    return Utilities.formatDate(value, tz, 'yyyy-MM-dd');
  }

  // Numbers or others: try construct Date
  const d = new Date(value);
  if (!isNaN(d.getTime())) {
    return Utilities.formatDate(d, tz, 'yyyy-MM-dd');
  }
  return null;
}


/**
 * Move yesterday's data to archive sheet
 */
function moveYesterdayData(sourceSheet, yesterdayDate, columnCount) {
  const lastRow = sourceSheet.getLastRow();
  if (lastRow <= 1) return 0; // No data rows
  const tz = Session.getScriptTimeZone();
  // Get all data with timestamps (Column A)
  const dataRange = sourceSheet.getRange(2, 1, lastRow - 1, columnCount);
  const allData = dataRange.getValues();

    // Filter yesterday's data quickly
  const yesterdayRows = [];
  for (let i = 0; i < allData.length; i++) {
    const row = allData[i];
    const key = _dateKeyFromCell(row[0], tz);
    if (key === yesterdayDate) yesterdayRows.push(row);
  }

  if (yesterdayRows.length === 0) {
    console.log(`No data found for ${yesterdayDate}`);
    return 0;
  }

  // Create archive sheet
  const archiveSheetName = `${yesterdayDate} ${sourceSheet.getName()}`;
  const archiveSheet = createArchiveSheet(archiveSheetName, sourceSheet.getName());

  // Copy yesterday's data to archive sheet
  if (yesterdayRows.length > 0) {
    archiveSheet.getRange(
      archiveSheet.getLastRow() + 1,
      1,
      yesterdayRows.length,
      columnCount
    ).setValues(yesterdayRows);
  }

  // Do NOT delete now; cleaning step will rebuild the sheet to today's rows in one pass.
  console.log(`Copied ${yesterdayRows.length} rows from ${yesterdayDate} to ${archiveSheetName}`);
  return yesterdayRows.length;
}

/**
 * Clean source sheet to keep only current day's data
 */
function cleanCurrentDayData(sourceSheet, todayDate) {
  const lastRow = sourceSheet.getLastRow();
  if (lastRow <= 1) return 0; // No data rows

  const lastCol = sourceSheet.getLastColumn();
  const tz = Session.getScriptTimeZone();

  // Get all data with timestamps (Column A)
  const dataRange = sourceSheet.getRange(2, 1, lastRow - 1, lastCol);
  const allData = dataRange.getValues();

  // Collect today's rows
  const todayRows = [];
  for (let i = 0; i < allData.length; i++) {
    const row = allData[i];
    const key = _dateKeyFromCell(row[0], tz);
    if (key === todayDate) todayRows.push(row);
  }

  const existingDataRows = lastRow - 1;
  const toDelete = existingDataRows - todayRows.length;

  // Rewrite today's rows in a single batch
  if (todayRows.length > 0) {
    sourceSheet.getRange(2, 1, todayRows.length, lastCol).setValues(todayRows);
  }

  // Delete any remaining trailing rows in one call
  if (toDelete > 0) {
    // Start position is the first row after the new data block
    const start = 2 + todayRows.length;
    // Guard against invalid ranges
    if (start <= lastRow) {
      sourceSheet.deleteRows(start, Math.min(toDelete, lastRow - start + 1));
    }
  } else if (todayRows.length === 0 && existingDataRows > 0) {
    // No rows for today: remove all data rows in one call
    sourceSheet.deleteRows(2, existingDataRows);
  }

  if (toDelete > 0) {
    console.log(`Deleted ${toDelete} old rows from ${sourceSheet.getName()}`);
  }

  return Math.max(0, toDelete);
}


/**
 * Create or get archive sheet with proper formatting
 */
function createArchiveSheet(archiveSheetName, sourceSheetName) {
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);

  // Check if archive sheet already exists
  let archiveSheet = ss.getSheetByName(archiveSheetName);
  if (archiveSheet) {
    console.log(`Archive sheet ${archiveSheetName} already exists, appending to it`);
    return archiveSheet;
  }

  // Create new archive sheet
  archiveSheet = ss.insertSheet(archiveSheetName);

  // Copy headers and formatting from source sheet
  const sourceSheet = ss.getSheetByName(sourceSheetName);
  if (sourceSheet && sourceSheet.getLastRow() >= 1) {
    // Copy header row
    const headerRow = sourceSheet.getRange(1, 1, 1, sourceSheet.getLastColumn()).getValues()[0];
    archiveSheet.appendRow(headerRow);

    // Apply header formatting
    const headerRange = archiveSheet.getRange(1, 1, 1, headerRow.length);
    headerRange.setFontWeight('bold');

    // Copy column widths from source sheet
    for (let col = 1; col <= sourceSheet.getLastColumn(); col++) {
      archiveSheet.setColumnWidth(col, sourceSheet.getColumnWidth(col));
    }
  } else {
    // Fallback headers for Environmental Data
    if (sourceSheetName === SHEET_NAME) {
      archiveSheet.appendRow([
        'Timestamp', 'Device ID', 'Temperature (°C)', 'Humidity (%)',
        'Pressure (hPa)', 'Gas Resistance (kOhms)', 'Device Timestamp', 'Firmware',
        'STINK Count', 'Redirect Count', 'Success Count', 'Total Requests',
        'Uptime Cycles', 'Reset Count'
      ]);
      archiveSheet.getRange(1, 1, 1, 14).setFontWeight('bold');
      archiveSheet.setColumnWidth(1, 180);
      archiveSheet.setColumnWidth(2, 120);
      archiveSheet.setColumnWidth(3, 140);
      archiveSheet.setColumnWidth(4, 140);
      archiveSheet.setColumnWidth(5, 140);
      archiveSheet.setColumnWidth(6, 180);
      archiveSheet.setColumnWidth(7, 180);
      archiveSheet.setColumnWidth(8, 140);
    }
    // Fallback headers for PICOMON
    else if (sourceSheetName === PICO_SHEET_NAME) {
      archiveSheet.appendRow([
        'Timestamp', 'Device ID', 'Core Temp (°C)', 'Raw ADC', 'Voltage (V)',
        'Device Timestamp', 'Firmware', 'STINK Count', 'Redirect Count',
        'Success Count', 'Total Requests', 'Uptime Cycles', 'Reset Count'
      ]);
      archiveSheet.getRange(1, 1, 1, 13).setFontWeight('bold');
      archiveSheet.setColumnWidth(1, 180);
      archiveSheet.setColumnWidth(2, 100);
      archiveSheet.setColumnWidth(3, 120);
      archiveSheet.setColumnWidth(4, 100);
      archiveSheet.setColumnWidth(5, 100);
      archiveSheet.setColumnWidth(6, 180);
      archiveSheet.setColumnWidth(7, 140);
    }
  }

  console.log(`Created archive sheet: ${archiveSheetName}`);
  return archiveSheet;
}

/**
 * Get archive state from Script Properties
 */
function _getArchiveState() {
  try {
    const raw = PropertiesService.getScriptProperties().getProperty(ARCHIVE_STATE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    console.error('Failed parsing archive state; resetting. Error:', e);
    return {};
  }
}

/**
 * Set archive state to Script Properties
 */
function _setArchiveState(state) {
  PropertiesService.getScriptProperties().setProperty(ARCHIVE_STATE_KEY, JSON.stringify(state));
}

/**
 * Create daily trigger for archiveDailyData()
 * Run once manually from the editor.
 */
function setupDailyArchiveTrigger() {
  // Remove existing archive triggers
  removeArchiveTriggers();

  // Create new trigger for 1:00 AM daily
  ScriptApp.newTrigger('archiveDailyData')
    .timeBased()
    .atHour(1)
    .everyDays(1)
    .create();

  console.log('Created time-driven trigger: archiveDailyData at 1:00 AM daily');
}

/**
 * Remove all archive triggers
 */
function removeArchiveTriggers() {
  const existing = ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'archiveDailyData');
  existing.forEach(t => ScriptApp.deleteTrigger(t));
  console.log(`Removed ${existing.length} archive trigger(s)`);
}

/**
 * Helper to set secrets once (edit values, run, then delete or comment out)
 */
function setupSecretsOnce() {
  // Edit these lines, run once, then remove this function.
  // PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', 'YOUR_SHEET_ID');
  // PropertiesService.getScriptProperties().setProperty('SLACK_WEBHOOK', 'https://hooks.slack.com/services/XXX/YYY/ZZZ');
  console.log('Secrets setter is a placeholder. Edit and run once if needed.');
}
