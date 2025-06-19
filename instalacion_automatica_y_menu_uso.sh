#!/bin/bash

# Variables
tor_password="mi_contraseña_segura"
repo_name="./"
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

start_program_no_tor() {
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
  nohup python3 controller.py --tor-disable 2>&1 | tee program.log &
  echo $! > "$pid_file"
  deactivate
}

start_program_no_tor_downloads() {
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
  nohup python3 controller.py --tor-disable --skip-download 2>&1 | tee program.log &
  echo $! > "$pid_file"
  deactivate
}

# Función para detener el programa
stop_program() {
  # Comprueba si está instalado
  if ! is_installed; then
    echo "El programa no está instalado."
    return 1
  fi

  # Lee el PID desde el archivo
  if [ -f "$pid_file" ]; then
    pid=$(<"$pid_file")
    # Verifica que el proceso exista
    if kill -0 "$pid" 2>/dev/null; then
      echo "Deteniendo el programa (PID $pid)…"
      # Primero SIGTERM
      kill "$pid"
      # Espera un poco a que termine “amablemente”
      for i in {1..5}; do
        if ! kill -0 "$pid" 2>/dev/null; then
          break
        fi
        sleep 1
      done
      # Si sigue vivo, matamos con SIGKILL
      if kill -0 "$pid" 2>/dev/null; then
        echo "No respondió a SIGTERM; forzando con SIGKILL…"
        kill -9 "$pid"
      fi
      # Borramos el archivo de PID
      rm -f "$pid_file"
    else
      echo "El PID en $pid_file ($pid) no corresponde a un proceso activo."
      rm -f "$pid_file"
    fi
  else
    echo "No se encontró el archivo de PID ($pid_file)."
  fi

  # Por si hay instancias “huérfanas” ejecutando controller.py con python3
  pids=$(pgrep -f "[p]ython3 controller\.py")
  if [ -n "$pids" ]; then
    echo "Detección de procesos adicionales: $pids"
    echo "Deteniendo instancias remanentes…"
    # Mismo tratamiento: SIGTERM y luego SIGKILL
    echo "$pids" | xargs -r kill
    sleep 1
    # Si quedan
    live=$(echo "$pids" | xargs -r -n1 sh -c 'kill -0 "$0" 2>/dev/null && printf "%s " "$0"' 2>/dev/null)
    if [ -n "$live" ]; then
      echo "Forzando con SIGKILL a: $live"
      echo "$live" | xargs -r kill -9
    fi
  else
    echo "No hay instancias remanentes de controller.py."
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
  echo "2. Descargar fichas e imagenes con tor"
  echo "3. Descargar solo fichas con tor"
  echo "4. Descargar fichas e imagenes sin tor"
  echo "5. Descargar solo fichas sin tor"
  echo "6. Detener programa"
  echo "7. Limpiar Redis"
  echo "8. Salir"
  read -p "Selecciona una opción: " option

  case $option in
    1) install_all ;;
    2) start_program ;;
    3) start_program_skip ;;
    4) start_program_no_tor ;;
    5) start_program_no_tor_downloads ;;
    6) stop_program ;;
    7) clean_redis ;;
    8) echo "Saliendo..."; exit 0 ;;
    *) echo "Opción no válida." ;;
  esac

done
