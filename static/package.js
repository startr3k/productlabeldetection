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

/*
 Gets the scanned label, this will evoke the /package hosted by Flask, which will then run DocAI.py
*/
async function readLabel()
{
  user = firebase.auth().currentUser;
  if (user) {
      document.getElementById('readLabelBtn').innerText = 'Scanning the label... Please wait';
      document.getElementById('readLabelBtn').disabled = true;
      selectedProduct = document.getElementById("labelme").value
      const token = await user.getIdToken();
      const response = await fetch('/package', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: `Bearer ${token}`,
        },
        body: 'img=' +selectedProduct +'&user=' +user.displayName, // send application data (vote)
      }).then (response => response.text())
      .then((response) => {
  
              document.documentElement.innerHTML = response
              document.getElementById('readLabelBtn').innerText = 'Read Label';
              document.getElementById('readLabelBtn').disabled = false;

              // although package.js was already included in the html, this needs to be done because creating a page with innerHTML
              // doesn't fire the js, while appending them again does
              var wrap = document.createElement('div');
              var scr = document.createElement('script');
              scr.src = '/package.js';
              scr.type = 'text/javascript';
              wrap.appendChild(scr);
              
              document.body.appendChild(wrap);
              tag = "[data-big='" +selectedProduct +"']";
              // this ensures that after the refresh the current product image is still selected
              document.querySelector(tag).click();


      }).catch ((error) => {
        console.log(`Error: ${error}`);
        window.alert('Something went wrong... Please try again!');
    });


  } else {
    window.alert('User not signed in.');
  }
}

/*
 Displays the product in the 'extract' div section
 First it takes the filename from the thumbnail selection, then it shows the actual sized image
 */
function displayProduct (el) 
{
    newSelection = el.getAttribute('data-big');
    img = document.getElementById('productlabel').style.content = "url(" +"https://storage.googleapis.com/ir0nmanproductlabel" +newSelection + ")";
    x = el.parentNode.getElementsByClassName('thumbnail');
    var i;
    for (i = 0; i < x.length; i++) 
    {
      x[i].classList.remove('selected');
    }
    el.classList.add('selected');
    document.getElementById('labelme').setAttribute('value',newSelection);
    prdLinked = document.getElementById('productLinked');
    if (prdLinked)
    {
        try
        {
            if ("/" +prdLinked.getAttribute('file').split(".")[0] != newSelection.split(".")[0])
            {
               document.getElementById('extract').innerHTML=""
            }
       }
       catch (err) {}
    }

}

