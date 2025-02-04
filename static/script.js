document.addEventListener('DOMContentLoaded', function(){
    // Connect to the SocketIO server.
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    var chatRoomDiv = document.getElementById('chat-room');
    var currentRoom = chatRoomDiv.getAttribute('data-room');
  
    // On connection, join the default room.
    socket.emit('join', {room: currentRoom});
  
    // Room switching: listen for button clicks.
    document.getElementById('commonRoomBtn').addEventListener('click', function(){
      switchRoom('common');
    });
    document.getElementById('privateRoomBtn').addEventListener('click', function(){
      switchRoom('private');
    });
  
    function switchRoom(room) {
      // Leave the current room.
      socket.emit('leave', {room: currentRoom});
      // Update current room.
      currentRoom = room;
      chatRoomDiv.setAttribute('data-room', currentRoom);
      document.getElementById('room-name').innerText = room.charAt(0).toUpperCase() + room.slice(1) + " Chat Room";
      // Join new room.
      socket.emit('join', {room: currentRoom});
      // Optionally clear chat messages for the new room.
      document.getElementById('messages').innerHTML = '';
    }
  
    // Handle sending text messages.
    document.getElementById('messageForm').addEventListener('submit', function(e){
      e.preventDefault();
      var messageInput = document.getElementById('messageInput');
      var message = messageInput.value.trim();
      if(message !== ''){
        socket.emit('text', {msg: message, room: currentRoom});
        messageInput.value = '';
      }
    });
  
    // Listen for incoming messages.
    socket.on('message', function(data){
      var msgDiv = document.createElement('div');
      msgDiv.innerHTML = data.msg;
      // If there is an attachment, display it.
      if(data.file_url){
        if(isImage(data.file_url)){
          var img = document.createElement('img');
          img.src = data.file_url;
          img.style.maxWidth = '200px';
          img.classList.add('mt-2');
          msgDiv.appendChild(document.createElement('br'));
          msgDiv.appendChild(img);
        } else if(isVideo(data.file_url)){
          var video = document.createElement('video');
          video.src = data.file_url;
          video.controls = true;
          video.style.maxWidth = '200px';
          video.classList.add('mt-2');
          msgDiv.appendChild(document.createElement('br'));
          msgDiv.appendChild(video);
        } else {
          var a = document.createElement('a');
          a.href = data.file_url;
          a.innerText = 'Download file';
          msgDiv.appendChild(document.createElement('br'));
          msgDiv.appendChild(a);
        }
      }
      document.getElementById('messages').appendChild(msgDiv);
      // Scroll to the bottom of the chat.
      document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
    });
  
    // Handle file attachment upload when the file input changes.
    document.getElementById('fileInput').addEventListener('change', function(){
      var file = this.files[0];
      if(file){
        var formData = new FormData();
        formData.append('file', file);
        formData.append('room', currentRoom);
        fetch('/upload', {
          method: 'POST',
          body: formData
        }).then(response => response.json())
        .then(data => {
          if(data.error){
            alert(data.error);
          }
        }).catch(err => {
          console.error(err);
        });
      }
      // Reset file input.
      this.value = '';
    });
  
    // Helper functions to check file types based on extension.
    function isImage(url){
      return(url.match(/\.(jpeg|jpg|gif|png)$/) != null);
    }
    function isVideo(url){
      return(url.match(/\.(mp4|mov|avi)$/) != null);
    }
  });
  