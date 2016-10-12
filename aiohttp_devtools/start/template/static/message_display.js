// some very basic javascript to populate the message board
// for simplicity this has no external requirements

var messages = document.getElementById('messages');

function request_state_changed() {
  if (this.readyState != 4) {
    return;
  }
  if (this.status != 200) {
    console.warn('error getting messages:', r);
    alert('error getting messages, response:' + this.status);
    return;
  }
  var data = JSON.parse(this.responseText);
  if (data.length == 0) {
    messages.innerHTML = 'No messages available.'
  } else {
    messages.innerHTML = '<ul>';
    data.forEach(function (m) {
      messages.innerHTML += '<li>' + m.username + ': <b>' + m.message + '</b>, (' + m.timestamp + ')</li>'
    });
    messages.innerHTML += '</ul>';
  }
}

var r = new XMLHttpRequest();
r.open('GET', messages.getAttribute('data-url'), true);
r.onreadystatechange = request_state_changed;
r.send('');
