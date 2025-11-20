pipeline {
    agent any

    environment {
        DJANGO_SETTINGS_MODULE = 'uniconnect.settings_auth'
    }

    options {
        skipStagesAfterUnstable()
        timestamps()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Set up Python') {
            steps {
                script {
                    def pythonCmd
                    if (isUnix()) {
                        def candidates = ['python3', 'python']
                        pythonCmd = candidates.find { sh(returnStatus: true, script: "command -v ${it} >/dev/null 2>&1") == 0 }
                        if (!pythonCmd) {
                            error 'Python is required on the Unix agent but was not found.'
                        }
                    } else {
                        def candidates = ['python', 'py -3', 'py']
                        pythonCmd = candidates.find { bat(returnStatus: true, script: "@${it} --version") == 0 }
                        if (!pythonCmd) {
                            error 'Python is required on the Windows agent but was not found. Ensure python or the py launcher is available in PATH.'
                        }
                    }

                    def venvPath = isUnix() ? "${env.WORKSPACE}/venv" : "${env.WORKSPACE}\\venv"
                    def venvPython = isUnix() ? "${venvPath}/bin/python" : "${venvPath}\\Scripts\\python.exe"
                    env.VENV = venvPath
                    env.VENV_PYTHON = venvPython

                    if (isUnix()) {
                        sh """
                            set -e
                            ${pythonCmd} -m venv "${venvPath}"
                            "${venvPython}" -m pip install --upgrade pip
                            "${venvPython}" -m pip install -r requirements.txt
                        """
                    } else {
                        bat """
                            ${pythonCmd} -m venv "${venvPath}"
                            "${venvPython}" -m pip install --upgrade pip
                            "${venvPython}" -m pip install -r requirements.txt
                        """
                    }
                }
            }
        }

        stage('Django checks (Auth)') {
            steps {
                script {
                    def venvPython = env.VENV_PYTHON

                    if (isUnix()) {
                        sh """
                            set -e
                            "${venvPython}" manage.py check --settings=${DJANGO_SETTINGS_MODULE}
                        """
                    } else {
                        bat """
                            "${venvPython}" manage.py check --settings=${DJANGO_SETTINGS_MODULE}
                        """
                    }
                }
            }
        }

        stage('Build auth-service image') {
            steps {
                script {
                    if (isUnix()) {
                        sh """
                            set -e
                            docker build -f services/auth_service/Dockerfile -t auth-service:latest .
                        """
                    } else {
                        bat """
                            docker build -f services/auth_service/Dockerfile -t auth-service:latest .
                        """
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
    }
}
