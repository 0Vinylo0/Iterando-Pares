#!/bin/bash

# Variables
tor_password="mi_contraseña_segura"
repo_name="/home/$(whoami)/Iterando-Pares"
script_dir="$(dirname "$0")"
venv_dir="$repo_name/env"
pid_file="$repo_name/program.pid"

# Función para manejar errores
die() {
  echo "$1" >&2
  exit 1
}

# Función para verificar si el programa está correctamente instalado
is_installed() {
  [ -f "$repo_name/controller.py" ] && [ -d "$venv_dir" ]
}

# Función para instalar todo
install_all() {
  if is_installed; then
    echo "El programa ya está instalado y listo para ejecutarse."
    return
  fi

  echo "[1/6] Actualizando el sistema e instalando dependencias..."
  sudo apt update || die "Error al actualizar los paquetes."
  sudo apt install -y git python3 python3-pip python3-venv redis-server tor curl || die "Error al instalar dependencias."

  echo "[2/6] Configurando TOR..."
  hashed_password=$(tor --hash-password "$tor_password") || die "Error al generar la contraseña hashed para TOR."
  sudo cp "$script_dir/torrc" /etc/tor/torrc || die "Error al reemplazar el archivo torrc."
  echo "\nHashedControlPassword $hashed_password" | sudo tee -a /etc/tor/torrc > /dev/null
  sudo systemctl restart tor || die "Error al reiniciar TOR."

  echo "[3/6] Configurando Redis..."
  sudo systemctl enable redis-server || die "Error al habilitar Redis."
  sudo systemctl start redis-server || die "Error al iniciar Redis."

  echo "[4/6] Creando entorno virtual e instalando dependencias de Python..."
  python3 -m venv "$venv_dir" || die "Error al crear el entorno virtual."
  chmod +x "$venv_dir/bin/activate" || die "Error al dar permisos al entorno virtual."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  pip install --upgrade pip || die "Error al actualizar pip."
  pip install -r "$repo_name/requirements.txt" || die "Error al instalar dependencias de Python."
  playwright install
  playwright install-deps
  deactivate

  echo "[5/6] Preparando archivo de URLs iniciales..."
  echo "https://pares.mcu.es/ParesBusquedas20/catalogo/description/1235" > "$repo_name/todo_urls.txt" || die "Error al crear el archivo todo_urls.txt."

  echo "[6/6] Verificando Redis y TOR..."
  redis-cli ping | grep -q PONG || die "Redis no está funcionando correctamente."
  curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org || die "TOR no está funcionando correctamente."

  echo "Instalación completada con éxito."
}

# Función para iniciar el programa
start_program() {
  if ! is_installed; then
    echo "El programa no está completamente instalado. Ejecuta la instalación primero."
    return
  fi

  if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
    echo "El programa ya está en ejecución."
    return
  fi

  echo "Iniciando el programa..."
  cd "$repo_name" || die "Error al acceder al directorio del repositorio."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  nohup python3 controller.py 2>&1 | tee program.log &
  echo $! > "$pid_file"
  deactivate
}

# Función para iniciar el programa sin descargas
start_program_skip() {
  if ! is_installed; then
    echo "El programa no está completamente instalado. Ejecuta la instalación primero."
    return
  fi

  if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
    echo "El programa ya está en ejecución."
    return
  fi

  echo "Iniciando el programa..."
  cd "$repo_name" || die "Error al acceder al directorio del repositorio."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  nohup python3 controller.py --skip-download 2>&1 | tee program.log &
  echo $! > "$pid_file"
  deactivate
}

# Función para detener el programa
stop_program() {
  if ! is_installed; then
    echo "El programa no está instalado."
    return
  fi

  if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
    echo "Deteniendo el programa..."
    kill $(cat "$pid_file") && rm -f "$pid_file"
  else
    echo "El programa no está en ejecución."
  fi
}

# Función para limpiar Redis
clean_redis() {
  if ! is_installed; then
    echo "El programa no está instalado. Por favor, instala primero."
    return
  fi

  stop_program

  echo "Limpiando Redis..."
  cd "$repo_name" || die "Error al acceder al directorio del repositorio."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  python3 delete.py || die "Error al ejecutar delete.py."
  deactivate
}

# Menú principal
while true; do
  echo "\nMenu Principal"
  echo "1. Instalar todo"
  echo "2. Iniciar programa"
  echo "3. Iniciar programa sin descargas"
  echo "4. Detener programa"
  echo "5. Limpiar Redis"
  echo "6. Salir"
  read -p "Selecciona una opción: " option

  case $option in
    1) install_all ;;
    2) start_program ;;
    3) start_program_skip ;;
    4) stop_program ;;
    5) clean_redis ;;
    6) echo "Saliendo..."; exit 0 ;;
    *) echo "Opción no válida." ;;
  esac

done
