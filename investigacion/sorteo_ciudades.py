"""
Sorteo de ciudades para el estudio de transferencia (investigacion/protocolo.md).

Reglas (fijadas antes del sorteo, investigacion/ciudades_candidatas.md):
    - Pittsburgh va fija a "aprender" (ya se vieron sus datos).
    - El examen principal lleva una ciudad de cada tipo: una grande, una mediana
      y una universitaria, cada una sorteada dentro de su tipo.
    - De las 5 restantes, 3 van a "aprender" y 2 a "practica", al azar.
    - Las listas se ordenan alfabeticamente antes de sortear, y se usa el
      generador de Python random.Random con el numero elegido por el autor, asi
      que cualquiera obtiene lo mismo con el mismo numero.

Ejecutar:
    python investigacion/sorteo_ciudades.py 4818
"""
import random
import sys

numero = int(sys.argv[1])
rng = random.Random(numero)
grandes = sorted(["Chicago", "Filadelfia", "Seattle"])
medianas = sorted(["Baton Rouge", "Cincinnati"])
universitarias = sorted(["Chapel Hill", "Gainesville", "Tempe"])

examen = [rng.choice(grandes), rng.choice(medianas), rng.choice(universitarias)]
resto = sorted(c for c in grandes + medianas + universitarias if c not in examen)
rng.shuffle(resto)
aprender = ["Pittsburgh"] + sorted(resto[:3])
practica = sorted(resto[3:])

print(f"Numero del sorteo: {numero} (Python {sys.version.split()[0]})")
print(f"Aprender:         {', '.join(aprender)}")
print(f"Practica:         {', '.join(practica)}")
print(f"Examen principal: {', '.join(examen)}")
