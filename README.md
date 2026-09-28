# CabinaFVHUnal

## 1. Descripción

Este repositorio contiene los archivos, diseños, datos y software desarrollados durante el proyecto **“Diseño e implementación de una cabina prototipo automatizada de bajo costo para la producción de Forraje Verde Hidropónico (FVH)”**.

El proyecto comprende el diseño y construcción de la cabina prototipo, los sistemas electrónicos y de control, el software de automatización, la interfaz de supervisión, AGRO-BOT, los diseños tridimensionales, los diseños de PCB, los datos de los ciclos de cultivo y el registro fotográfico del desarrollo del proyecto.

## 2. Recursos del proyecto

- **Video de funcionamiento:** [Ver video en YouTube](https://www.youtube.com/playlist?list=PLa2235HGgJpQ)
- **Dashboard remoto:** [Acceder al dashboard](https://cabinafvh.duckdns.org/dashboard/page1)
- **Repositorio complementario:** [Consultar archivos en Google Drive](https://drive.google.com/drive/folders/1n4Momb2bnFOUJLxZTVhM5PK6ztII8chc?usp=drive_link)

## 3. Organización del repositorio

La información se encuentra organizada en las siguientes carpetas:

- **Data Ciclos Cultivo:** datos registrados durante los ciclos experimentales, archivos consolidados y scripts de procesamiento y auditoría.
- **Diseños 3D:** modelos tridimensionales de la cabina, sus sistemas y componentes individuales, en formatos F3D y STEP.
- **Interfaz Node-RED y AGRO-BOT:** archivos JSON correspondientes a los flujos de Node-RED y AGRO-BOT.
- **KiCad PCB:** proyectos de KiCad correspondientes a las PCB principal, de potencia y de sensores.
- **Python - Scripts de Control:** software de control ejecutado en la Raspberry Pi y archivos de datos utilizados por el sistema.
- **Registro Fotográfico:** registro visual de la construcción de la cabina y de los ciclos de cultivo.

Cada carpeta contiene un README específico con información sobre su contenido y organización.

## 4. Plataforma de control

El sistema de control fue implementado sobre una **Raspberry Pi 3B+**, utilizando Python como base para la ejecución de las funciones de automatización y control.

La arquitectura desarrollada también integra herramientas como Node-RED, Mosquitto e InfluxDB para las funciones de supervisión, comunicación y almacenamiento de información.

## 5. Reproducción de los archivos

Los archivos proporcionados permiten consultar y reproducir los diferentes desarrollos realizados durante el proyecto.

### Software de control

La estructura de la carpeta `Python - Scripts de Control` debe conservarse para mantener correctamente las relaciones entre el archivo principal y los módulos utilizados.

El archivo principal es:

```text
main2.py
```

Para ejecutar el sistema de control en la Raspberry Pi:

```bash
sudo python3 main2.py
```

El uso de `sudo` es necesario debido a los requerimientos de acceso al hardware utilizados para el control de la iluminación mediante LEDs WS2812B.

### Flujos de Node-RED

Los flujos de Node-RED pueden reproducirse mediante la opción de **Importar** de Node-RED a partir de los archivos JSON proporcionados en `Interfaz Node-RED y AGRO-BOT`.

### Diseños 3D

Los archivos F3D pueden abrirse y editarse mediante Autodesk Fusion 360. Los archivos STEP permiten la visualización e interoperabilidad con otros programas de diseño asistido por computador.

### Diseños PCB

Los proyectos contenidos en `KiCad PCB` pueden abrirse mediante KiCad conservando los archivos propios de cada proyecto.

### Datos experimentales

Los archivos de `Data Ciclos Cultivo` contienen tanto los registros originales como los archivos consolidados y los scripts utilizados para su procesamiento y auditoría.

## 6. Datos y documentación

Los datos, diseños y archivos de software contenidos en este repositorio corresponden a los desarrollos realizados durante el proyecto y constituyen el soporte técnico y experimental de la tesis.

La documentación se complementa con el documento de tesis, donde se presentan el diseño, implementación, metodología, validación y resultados obtenidos.

## 7. Requisitos generales

La reproducción completa del sistema físico requiere la plataforma de hardware y los componentes utilizados durante el desarrollo del prototipo.

Para la reproducción de los archivos digitales se requieren las herramientas correspondientes a cada tipo de recurso, entre ellas:

- Raspberry Pi OS y Python para el software de control.
- Node-RED para los flujos de supervisión y control.
- KiCad para los diseños de PCB.
- Autodesk Fusion 360 u otro software compatible para los modelos 3D.
- Herramientas compatibles con archivos CSV y JSON para la consulta de datos.

## 8. Alcance

Este repositorio tiene como finalidad conservar y facilitar la consulta, trazabilidad y reproducción de los principales recursos desarrollados durante el proyecto de la cabina prototipo automatizada para producción de FVH.