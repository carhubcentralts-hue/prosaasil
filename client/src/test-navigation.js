// Test file to debug navigation
console.log('Testing navigation...');
console.log('Current location:', window.location.href);
console.log('React Router available:', !!window.ReactRouter);

// Test direct navigation
function testNav() {
  console.log('Testing navigation to /admin/crm');
  window.location.href = '/admin/crm';
}

window.testNav = testNav;