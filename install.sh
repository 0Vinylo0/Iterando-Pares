#!/bin/bash

# Variables
tor_password="mi_contraseña_segura"
repo_url="https://github.com/0Vinylo0/Iterando-Pares/"
repo_name="$(basename -s .git "$repo_url")"
venv_dir="env"
pid_file="program.pid"

# Función para manejar errores
die() {
  echo "$1" >&2
  exit 1
}

# Función para verificar si el programa ya está instalado
is_installed() {
  if [ -d "$repo_name" ]; then
    return 0
  else
    return 1
  fi
}

# Función para instalar todo
install_all() {
  if [ -d "$repo_name" ]; then
    echo "El programa ya está instalado."
    return
  fi

  echo "[1/8] Actualizando el sistema e instalando dependencias..."
  sudo apt update || die "Error al actualizar los paquetes."
  sudo apt install -y git python3 python3-pip python3-venv redis-server tor || die "Error al instalar dependencias."

  echo "[2/8] Clonando el repositorio..."
  git clone "$repo_url" || die "Error al clonar el repositorio."
  cd "$repo_name" || die "Error al acceder al directorio del repositorio."

  echo "[3/8] Configurando TOR..."
  hashed_password=$(tor --hash-password "$tor_password") || die "Error al generar la contraseña hashed para TOR."
  sudo cp torrc /etc/tor/torrc || die "Error al reemplazar el archivo torrc."
  echo "\nHashedControlPassword $hashed_password" | sudo tee -a /etc/tor/torrc > /dev/null
  sudo systemctl restart tor || die "Error al reiniciar TOR."

  echo "[4/8] Configurando Redis..."
  sudo systemctl enable redis-server || die "Error al habilitar Redis."
  sudo systemctl start redis-server || die "Error al iniciar Redis."

  echo "[5/8] Creando entorno virtual e instalando dependencias de Python..."
  python3 -m venv "$venv_dir" || die "Error al crear el entorno virtual."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  pip install --upgrade pip || die "Error al actualizar pip."
  pip install -r requirements.txt || die "Error al instalar dependencias de Python."
  deactivate

  echo "[6/8] Preparando archivo de URLs iniciales..."
  echo "https://pares.mcu.es/ParesBusquedas20/catalogo/description/1235" > todo_urls.txt || die "Error al crear el archivo todo_urls.txt."

  echo "[7/8] Verificando Redis y TOR..."
  redis-cli ping | grep -q PONG || die "Redis no está funcionando correctamente."
  curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org || die "TOR no está funcionando correctamente."

  echo "Instalación completada con éxito."
}

# Función para iniciar el programa
start_program() {
  if ! [ -d "$repo_name" ]; then
    echo "El programa no está instalado. Por favor, instala primero."
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
  cd ..
}

# Función para detener el programa
stop_program() {
  cd $repo_name
  if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
    echo "Deteniendo el programa..."
    kill $(cat "$pid_file") && rm -f "$pid_file"
  else
    echo "El programa no está en ejecución."
  fi
  ls
  cd ..
}

# Función para limpiar Redis
clean_redis() {
  if ! [ -d "$repo_name" ]; then
    echo "El programa no está instalado. Por favor, instala primero."
    return
  fi

  stop_program

  echo "Limpiando Redis..."
  cd "$repo_name" || die "Error al acceder al directorio del repositorio."
  . "$venv_dir/bin/activate" || die "Error al activar el entorno virtual."
  python3 delete.py || die "Error al ejecutar delete.py."
  deactivate
  cd ..
}

# Menú principal
while true; do
  echo "\nMenu Principal"
  echo "1. Instalar todo"
  echo "2. Iniciar programa"
  echo "3. Detener programa"
  echo "4. Limpiar Redis"
  echo "5. LS"
  echo "6. Salir"
  read -p "Selecciona una opción: " option

  case $option in
    1) install_all ;;
    2) start_program ;;
    3) stop_program ;;
    4) clean_redis ;;
    5) ls ;;
    6) echo "Saliendo..."; exit 0 ;;
    *) echo "Opción no válida." ;;
  esac
done
