const pista = document.querySelector('.carrusel-pista');
const imagenes = document.querySelectorAll('.carrusel-imagen');
const btnIzquierda = document.querySelector('.carrusel-btn.izquierda');
const btnDerecha = document.querySelector('.carrusel-btn.derecha');

let indice = 0;

function moverA(n) {
    indice = (n + imagenes.length) % imagenes.length;
    pista.style.transform = `translateX(-${indice * 100}%)`;
}

btnDerecha.addEventListener('click', () => moverA(indice + 1));
btnIzquierda.addEventListener('click', () => moverA(indice - 1));

// setInterval(() => moverA(indice + 1), 3000);  ← eliminado