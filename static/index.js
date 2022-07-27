var request_object = {
    method: "GET",
    mode: "cors",
    cache: "no-cache", 
    credentials: "same-origin",
    redirect: 'follow',
    referrer: "no-referrer",
    headers: {'Content-Type': 'application/json'}
}

function revise(){
    let user = JSON.parse(localStorage.getItem("user"))
    Object.keys(user).forEach(function(key) {
        let es = document.getElementsByClassName(key);
        for (let i = 0; i < es.length; i++) {
            es[i].innerHTML=user[key]
        }
    })
}

async function getUser(){
    document.getElementById("load").style.visibility = "visible";
    let response = await fetch('/getuser');
    let user = await response.json();
    localStorage.setItem("user", JSON.stringify(user))

    document.getElementById("load").style.visibility = "hidden";
    showToast("Hi "+ user.first_name +"! Welcome to Flash Card Application", "bg-primary")
    revise()
}

async function getPage(url){
    fetch('/cleardata')
    document.getElementById("load").style.visibility = "visible";
    if(localStorage.getItem("user") === null){
        await getUser()
        getPage(url)
        return
    }

    let response = await fetch(url)
    if(response.status >=400 && response.status < 500){
        document.getElementById("zone").innerHTML = await response.text()
        return
    }
    if(response.redirected){
        window.location.href = response.url
        return
    }

    let page_data = await response.json()
    history.pushState({}, page_data['title'], url)
    document.getElementById("navtitle").innerHTML = page_data['header'];
    document.title = page_data['title']
    document.getElementById("zone").innerHTML = page_data['content']
    localStorage.setItem("index", String(page_data['index']))

    revise()
    document.getElementById("load").style.visibility = "hidden";
}

window.onload = function(){
    getUser()
}

async function Zone(args, method='GET', action){
    document.getElementById("load").style.visibility = "visible";
    let response = ""
    let curl = window.location.href
    switch(localStorage.getItem("index")){
        case "0": response = await trainingRequest("/training?" + args, method); break
        case "1": response = await decksRequest("/decks?" + args, method);break
        case "2": response = await exploreRequest("/explore?" + args, method); break
        default: break
    }
    if(response === ""){
        getPage(curl)
        return
    }
    if(response !== undefined){
        if(action === 'append')document.getElementById("zone").insertAdjacentHTML("beforeend", response)
        else if(action === 'replace')document.getElementById("zone").innerHTML = response
    }
    document.getElementById("load").style.visibility = "hidden";
}

async function decksRequest(url, method){
    request_object.method = method

    if(method === 'POST'){
        let data = new Object()
        let form = new FormData(document.getElementById("deckform"))
        let cards = document.getElementsByClassName("cardform")
        form.forEach(function(value, key){data[key] = value})
        if(data['name'] === "" || (data['genre'] === "" && data['newgenre'] === "") || cards.length === 0){
            showToast("Please fill out the necessary fields. Required: Name of deck, Genre of Deck and at least 1 card in this deck", "bg-danger")
            return
        }
        let cards_array = []
        for(let i = 0; i < cards.length; i++){
            cards_array.push(new Object({
                'state': cards[i].querySelector("#state").value,
                'question': cards[i].querySelector("#cq").value,
                'answer': cards[i].querySelector("#ca").value
            }))
        }
        for(let i = 0; i < cards.length; i++){
            if(cards_array[i]['state'] == 'old'){
                cards_array[i]['cid'] = cards[i].querySelector("#cid").value
            }
        }
        data['cards'] = cards_array
        console.log(data)
        request_object['body'] = JSON.stringify(data)
    }

    let response = await fetch(url, request_object);
    delete request_object["body"]
    if(method == 'GET')
        return await response.text()
    else if(method == 'POST'){
        let msg = await response.text()
        if(response.status == 201) showToast(msg, "bg-success")
        else showToast(msg, "bg-danger")
        return ""
    }else if(method == 'DELETE'){
        let msg = await response.text()
        if(response.status == 200 || response.status == 202) showToast(msg, "bg-success")
        else showToast(msg, "bg-danger")
        if(response.status == 200)return ""
        else return null
    }
}

async function exploreRequest(url, method){
    request_object.method = method
    let response = await fetch(url, request_object);
    if(method == "PUT"){
        let msg = await response.text()
        if(response.status == 200)showToast(msg, "bg-success")
        else showToast(msg, "bg-danger")

        return ""
    }
}

async function trainingRequest(url, method){
    request_object.method = method
    let response = await fetch(url, request_object)
    if(method == "GET"){
        let res = await response.json()
        if(res['page']){
            fetch("/training?rtype=next").then(response=>response.json()).then(data => {
                if(data['next'])document.getElementById("getnext").disabled = false
                else document.getElementById("getnext").disabled = true
                document.getElementById("getprev").disabled = true
                document.getElementById("training_pane").innerHTML = data['this']
            })
            return res['page']
        }
        else if(res['this']){
            if(res['prev'])document.getElementById("getprev").disabled = false
            else document.getElementById("getprev").disabled = true
            if(res['next'])document.getElementById("getnext").disabled = false
            else document.getElementById("getnext").disabled = true
            document.getElementById("training_pane").innerHTML = res['this']
            return null
        }
    }
    else if(method == 'POST'){
        let res = await response.json()
        if('valid' in res){
            let choices = document.getElementsByClassName("choice")
            for(let i=0; i<choices.length; i++){
                choices.item(i).disabled = true
            }

            if(res['valid'] === true){
                choices.item(res['correct_id']).classList.add("bg-success")
                showToast("Yes! You've choosen the correct option!", "bg-success")
            }
            else{
                choices.item(res['correct_id']).classList.add("bg-success")
                choices.item(res['option_id']).classList.add("bg-danger")
                showToast("Unfortunately, You've got it incorrect! Try again next time!", "bg-danger")
            }
            document.getElementById("card-att").innerHTML = res['c_att']
            document.getElementById("card-rem").innerHTML = res['c_rem']
            return null
        }
    }
}

function showToast(msg, context_colour){
    var toast = document.getElementById("toast")
    toast.classList.add(context_colour)
    document.getElementById("toastmsg").innerHTML = msg
    toast.classList.replace("hide", "show")
    setTimeout(function() {
        toast.classList.replace("show", "hide")
        toast.classList.remove(context_colour)
    }, msg.length*100);
}