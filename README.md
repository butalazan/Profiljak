
Airfoil-SU2 paket za analizo 2D profilov v netrivialnih konfiguracijah.
![Simulacija toka](eppler376_flow.gif)

# Navodila za namestitev SU2 (Windows)


## Potrebščine:
   - WSL (Windows Subsystem for Linux) ali Linux/Mac OS - v slednjem primeru spustimo prvi korak,
   - python 3.8 ali novejši s knjižnjicami numpy, os, glob, pyvista,
   - gmsh - program za generiranje mrež,
   - SU2 - delovni konj.

## Nameščanje WSL

1. Zaženemo PowerShell kot skrbnik (Win + X + A  ->  PowerShell (Admin)),
2. Vnesemo ukaz:

   `wsl --install`

3. Če je potrebno, znova zaženemo PC. Po ponovnem zagonu zaženemo Ubuntu (WSL) in nastavimo uporabniško ime ter geslo zanj.

## Nameščanje paketov (od tukaj dalje delamo v terminalu Ubuntu (WSL))

Zaženemo ukaza:

   `sudo apt update && sudo apt install -y
      build-essential cmake python3 python3-pip
      libopenmpi-dev openmpi-bin git`

in:

   `pip3 install pyvista`

## Nalaganje SU2

Prenesemo in namestimo SU2, kot velevajo navodila na njih spletni strani:
   https://su2code.github.io/download.html

ali preprosto zaženemo:

   `git clone https://github.com/su2code/SU2.git
   cd SU2`

## Prevajanje SU2

Zaženemo Makefile, ki prevede SU2 kodo:

   `mkdir build`\
   `cd build`\
   `cmake ..`\
   `make -j$(nproc)`

## Dodajanje sistemske poti (PATH)

Zaženemo:

   `echo 'export PATH=$PATH:$HOME/SU2/bin' >> ~/.bashrc
   source ~/.bashrc`

To omogoči uporabo SU2 ukazov iz katere koli mape.


## Dokumentacija: 
https://su2code.github.io/docs_v7/home/





# Navodila za uporabo Airfoil paketa

V CAD programu narišemo poljuben profil, ter koordinate točk izvozimo v tekstovno datoteko .dat.


Zaženemo batch file airfoil2D.bat
Odpre se okno, ki nas vodi po korakih:
   - vnesemo imena datotek s koordinatami profilov (največ 5)
   - vnesemo vpadni kot v stopinjah,
   - vnesemo ime za bodoče izvožene datoteke (po potrebi)
   - vnesemo Reynoldsovo dolžino in hitrost za izračun Re (po potrebi, default je 85000)

![SU2 Interface](su2_interface.png)

Program generira mrežo in požene simulacijo, ki lahko traja nekaj ur.
Output so mape:
   - profil1
      - vtus
      - dats
      - slike
      - rezultati

SU2 je prirejen za osnovno reševanje tranzientnega Navier-Stokes sistema (URANS) s turbolenčnim modelom Salbart-Allarmas.

![SU2 Vmesnik](interface.png)
