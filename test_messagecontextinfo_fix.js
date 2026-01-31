#!/usr/bin/env node
/**
 * Test to verify that messages with messageContextInfo are not filtered out
 * This is a critical fix for WhatsApp message handling
 */

// Read the baileys_service.js file and extract the extractText function
const fs = require('fs');
const path = require('path');

const serviceFile = path.join(__dirname, 'services', 'whatsapp', 'baileys_service.js');
const content = fs.readFileSync(serviceFile, 'utf8');

// Extract the extractText function using regex
const extractTextMatch = content.match(/function extractText\(msgObj\) \{[\s\S]*?\n\}/);
if (!extractTextMatch) {
  console.error('❌ Could not find extractText function');
  process.exit(1);
}

// Create a safe eval environment
const extractTextCode = extractTextMatch[0];
eval(extractTextCode);

console.log('🧪 Testing messageContextInfo fix...\n');

// Test Case 1: Message with conversation and messageContextInfo should NOT be filtered
const testCase1 = {
  conversation: "נראלך לא נספיק לסיים עד מחר?",
  messageContextInfo: {
    deviceListMetadata: {},
    deviceListMetadataVersion: 2
  }
};

const result1 = extractText(testCase1);
console.log('Test 1: Message with conversation and messageContextInfo');
console.log(`  Input: conversation="${testCase1.conversation}", messageContextInfo=present`);
console.log(`  Expected: "${testCase1.conversation}"`);
console.log(`  Got: "${result1}"`);

if (result1 === testCase1.conversation) {
  console.log('  ✅ PASS - Message correctly extracted\n');
} else {
  console.log('  ❌ FAIL - Message was incorrectly filtered\n');
  process.exit(1);
}

// Test Case 2: Message with ONLY messageContextInfo should still be filtered
const testCase2 = {
  messageContextInfo: {
    deviceListMetadata: {},
    deviceListMetadataVersion: 2
  }
};

const result2 = extractText(testCase2);
console.log('Test 2: Message with ONLY messageContextInfo (no actual content)');
console.log(`  Input: messageContextInfo=present, no text content`);
console.log(`  Expected: null`);
console.log(`  Got: ${result2}`);

if (result2 === null) {
  console.log('  ✅ PASS - Non-message correctly filtered\n');
} else {
  console.log('  ❌ FAIL - Non-message should have been filtered\n');
  process.exit(1);
}

// Test Case 3: Regular message without messageContextInfo should work
const testCase3 = {
  conversation: "Hello, this is a test"
};

const result3 = extractText(testCase3);
console.log('Test 3: Regular message without messageContextInfo');
console.log(`  Input: conversation="${testCase3.conversation}"`);
console.log(`  Expected: "${testCase3.conversation}"`);
console.log(`  Got: "${result3}"`);

if (result3 === testCase3.conversation) {
  console.log('  ✅ PASS - Regular message works correctly\n');
} else {
  console.log('  ❌ FAIL - Regular message failed\n');
  process.exit(1);
}

// Test Case 4: Protocol message should be filtered (even with text)
const testCase4 = {
  protocolMessage: {
    type: 0
  },
  conversation: "This should be filtered"
};

const result4 = extractText(testCase4);
console.log('Test 4: Protocol message should be filtered');
console.log(`  Input: protocolMessage=present, conversation="${testCase4.conversation}"`);
console.log(`  Expected: null`);
console.log(`  Got: ${result4}`);

if (result4 === null) {
  console.log('  ✅ PASS - Protocol message correctly filtered\n');
} else {
  console.log('  ❌ FAIL - Protocol message should have been filtered\n');
  process.exit(1);
}

console.log('🎉 All tests passed!');
console.log('\n✅ FIX VERIFIED: Messages with messageContextInfo are now correctly processed');
