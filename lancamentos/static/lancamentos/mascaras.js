function mascaraDinheiro(input) {
    input.addEventListener("input", () => {
        const digitos = input.value.replace(/\D/g, "").slice(0, 9);
        if (!digitos) {
            input.value = "";
            return;
        }
        const numero = parseInt(digitos, 10) / 100;
        input.value = numero.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    });
}

function mascaraData(input) {
    input.addEventListener("input", () => {
        const d = input.value.replace(/\D/g, "").slice(0, 8);
        let saida = d;
        if (d.length > 4) {
            saida = d.slice(0, 2) + "/" + d.slice(2, 4) + "/" + d.slice(4);
        } else if (d.length > 2) {
            saida = d.slice(0, 2) + "/" + d.slice(2);
        }
        input.value = saida;
    });
}

document.querySelectorAll('[data-mascara="dinheiro"]').forEach(mascaraDinheiro);
document.querySelectorAll('[data-mascara="data"]').forEach(mascaraData);



function mascaraCpf(input) {
    input.addEventListener("input", () => {
        const d = input.value.replace(/\D/g, "").slice(0, 11);
        let saida = d;
        if (d.length > 9) {
            saida = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
        } else if (d.length > 6) {
            saida = d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
        } else if (d.length > 3) {
            saida = d.slice(0, 3) + "." + d.slice(3);
        }
        input.value = saida;
    });
}

document.querySelectorAll('[data-mascara="cpf"]').forEach(mascaraCpf);