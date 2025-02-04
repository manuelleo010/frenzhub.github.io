document.addEventListener('DOMContentLoaded', function(){
    // Connect to the SocketIO server.
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
    var chatRoomDiv = document.getElementById('chat-room');
    // Initially, the current room is "common".
    var currentRoom = chatRoomDiv.getAttribute('data-room');
  
    // On connection, join the default (common) room.
    socket.emit('join', {room: currentRoom});
  
    // ---------------------------
    // Online Users List Handling
    // ---------------------------
    var onlineUsersDiv = document.getElementById('online-users');
    function updateOnlineUsers(users) {
      // Clear the current list.
      onlineUsersDiv.innerHTML = '<h5>Online Users</h5>';
      // Create a list of users (exclude the current user).
      users.forEach(function(user) {
        if(user === document.getElementById('current-username').innerText) return;
        var userElem = document.createElement('div');
        userElem.classList.add('online-user');
        userElem.innerText = user;
        // When a user clicks on another username, start a private chat.
        userElem.addEventListener('click', function(){
          socket.emit('start_private', {target: user});
        });
        onlineUsersDiv.appendChild(userElem);
      });
    }
  
    // Listen for online_users event from the server.
    socket.on('online_users', function(users) {
      updateOnlineUsers(users);
    });
  
    // ---------------------------
    // Room switching buttons (common chat)
    // ---------------------------
    document.getElementById('commonRoomBtn').addEventListener('click', function(){
      switchRoom('common');
    });
  
    // Private chat room switching is handled when a private chat is started.
  
    function switchRoom(room) {
      // Leave the current room.
      socket.emit('leave', {room: currentRoom});
      // Update the current room.
      currentRoom = room;
      chatRoomDiv.setAttribute('data-room', currentRoom);
      document.getElementById('room-name').innerText = room.startsWith('private_')
        ? "Private Chat: " + room.replace('private_', '').replace('_', ' & ')
        : room.charAt(0).toUpperCase() + room.slice(1) + " Chat Room";
      // Join the new room.
      socket.emit('join', {room: currentRoom});
      // Clear chat messages.
      document.getElementById('messages').innerHTML = '';
    }
  
    // Listen for the "private_started" event (when the local user initiated a private chat).
    socket.on('private_started', function(data){
      switchRoom(data.room);
    });
  
    // Listen for the "initiate_private" event (when another user starts a private chat with you).
    socket.on('initiate_private', function(data){
      // Automatically join the private room and switch chat window.
      switchRoom(data.room);
      // Optionally, show a notification that a private chat has been initiated.
      var messagesDiv = document.getElementById('messages');
      var notice = document.createElement('div');
      notice.classList.add('text-info');
      notice.innerText = data.sender + " has started a private chat with you.";
      messagesDiv.appendChild(notice);
    });
  
    // ---------------------------
    // Sending text messages
    // ---------------------------
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
  
    // ---------------------------
    // File attachment upload handling
    // ---------------------------
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
  
    // Helper functions to check file types.
    function isImage(url){
      return(url.match(/\.(jpeg|jpg|gif|png)$/) != null);
    }
    function isVideo(url){
      return(url.match(/\.(mp4|mov|avi)$/) != null);
    }
  });
  