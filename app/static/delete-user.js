"use strict"

function fillModal(event) {
    let deleteUrl = event.relatedTarget.dataset.deleteUrl;
    let modalForm = event.target.querySelector("form");
    modalForm.action = deleteUrl;
    let fullName = event.relatedTarget.dataset.fullName;
    let modalBody = event.target.querySelector(".modal-body");
    modalBody.innerHTML = `<p>Вы уверены, что хотите удалить пользователя ${fullName}?</p>`;
}

window.onload = function () {
    let deleteModal = document.getElementById("delete-modal");
    deleteModal.addEventListener("show.bs.modal", fillModal);
}