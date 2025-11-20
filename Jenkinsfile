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
                    def pythonCmd = isUnix() ? 'python3' : 'python'
                    def venvPath = isUnix() ? "${env.WORKSPACE}/venv" : "${env.WORKSPACE}\\venv"
                    env.VENV = venvPath

                    if (isUnix()) {
                        sh """
                            set -e
                            ${pythonCmd} -m venv "${venvPath}"
                            . "${venvPath}/bin/activate"
                            pip install --upgrade pip
                            pip install -r requirements.txt
                        """
                    } else {
                        bat """
                            ${pythonCmd} -m venv "${venvPath}"
                            call "${venvPath}\\Scripts\\activate"
                            pip install --upgrade pip
                            pip install -r requirements.txt
                        """
                    }
                }
            }
        }

        stage('Django checks (Auth)') {
            steps {
                script {
                    def venvPath = env.VENV

                    if (isUnix()) {
                        sh """
                            set -e
                            . "${venvPath}/bin/activate"
                            python manage.py check --settings=${DJANGO_SETTINGS_MODULE}
                        """
                    } else {
                        bat """
                            call "${venvPath}\\Scripts\\activate"
                            python manage.py check --settings=${DJANGO_SETTINGS_MODULE}
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
