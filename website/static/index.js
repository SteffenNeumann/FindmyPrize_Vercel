function deleteNote(noteId) {
  fetch("/delete-note", {
    method: "POST",
    body: JSON.stringify({ noteId: noteId }),
  }).then((_res) => {
    window.location.href = "/";
  });
}

function updateDealsList() {
    fetch('/get-deals')
        .then(response => response.json())
        .then(deals => {
            const dealsContainer = document.querySelector('.row-cols-1');
            // Update deals display
            renderDeals(deals);
        });
}

setInterval(updateDealsList, 300000); // Update every 5 minutes
