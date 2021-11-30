/**
 * Copyright 2021 Google LLC
 * Licensed under the Apache License, Version 2.0 (the `License`);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an `AS IS` BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

firebase.initializeApp(config);

/*
 Login via email/password in Firebase. Use must be created in Identity Platform/Firebase
*/
function signIn() {

  var email = document.getElementById('username').value;
  var password = document.getElementById('password').value;

  const provider = new firebase.auth.GoogleAuthProvider();
  provider.addScope('https://www.googleapis.com/auth/userinfo.email');
  document.getElementById('signInButton').innerText = 'Logging in...';

  firebase
  .auth()
  //.signInWithPopup(provider)
  .signInWithEmailAndPassword(email, password)
  .then(result => {

      console.log(`${result.user.email} logged in.`);
      //window.alert(`Welcome ${result.user.displayName}!`);
      fly_away(result.user);


  }).catch(err => {
      console.log(`Error during sign in: ${err.message}`);
      document.getElementById('signInButton').innerText = 'login';
      window.alert(`Sign in failed. Retry or check your browser logs.`);
  });

}

/*
 Login via Google account in Firebase. User must be created in Identity Platform/Firebase
 Using Google as the IdP, new accounts are automatically created
 That's why the users are verified against Datastore to be the legit ones first (see main.py)
*/
function signInGoogle() {

  const provider = new firebase.auth.GoogleAuthProvider();
  provider.addScope('https://www.googleapis.com/auth/userinfo.email');
  document.getElementById('signInButton').innerText = 'Logging in...';
  var displayName = '';
  var user = '';

  firebase
  .auth()
  .signInWithPopup(provider)
  //.signInWithEmailAndPassword(email, password)
  .then(result => {

      displayName = result.user.displayName;
      user = result.user;

      return fetch('/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'email=' +result.user.email, // send application data (vote)
      })

  }).then (response => response.text())
  .then((response) => {

      if (response == "1") {

          console.log(`${displayName} logged in.`);
          fly_away(user);

      }
      else {

          console.log(`User doest not exist.`);
          document.getElementById('signInButton').innerText = 'login';
          window.alert(`You have not been granted access. Please reach out to administrator to request.`);

      }

  }).catch(err => {
      console.log(`Error during sign in: ${err.message}`);
      document.getElementById('signInButton').innerText = 'login';
      window.alert(`Sign in failed. Retry or check your browser logs.`);
  });

}

function signOut() {
  firebase
    .auth()
    .signOut()
    .then(result => {})
    .catch(err => {
      console.log(`Error during sign out: ${err.message}`);
      window.alert(`Sign out failed. Retry or check your browser logs.`);
    });
}

/*
 After logging in, straight away get the list of product images and display them
*/
async function fly_away(user) {
  //user = firebase.auth().currentUser;

  if (user) {
    try {
      // token is needed to authorize access, and needs to be part of the header request. Same throughout the code
      const token = await user.getIdToken();
      const response = await fetch('/package', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const text = await response.text();
        document.documentElement.innerHTML = text

        // although package.js was already included in the html, this needs to be done because creating a page with innerHTML
        // doesn't fire the js, while appending them again does
        var wrap = document.createElement('div');
        var scr = document.createElement('script');
        scr.src = '/package.js';
        scr.type = 'text/javascript';
        wrap.appendChild(scr);

        document.body.appendChild(wrap);

      }
    } catch (err) {
      console.log(`Error: ${err}`);
      window.alert('Something went wrong... Please try again!');
    }
  } else {
    window.alert('User not signed in.');
  }
}


