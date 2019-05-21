// some very basic javascript to populate the message board
// for simplicity this has no external requirements

const messages = document.getElementById('messages')

fetch(messages.getAttribute('data-url'))
  .then(r => {
    if (r.status !== 200) {
      console.warn('error getting messages:', r)
      alert('error getting messages, response:' + this.status)
    } else {
      r.json().then(data => {
        if (data.length === 0) {
          messages.innerHTML = 'No messages available.'
        } else {
          messages.innerHTML = '<ul>'
          messages.innerHTML += data.map(m => `<li>${m.username}: <b>${m.message}</b>, (${m.timestamp})</li>`).join('')
          messages.innerHTML += '</ul>'
        }
      })
    }
  })
