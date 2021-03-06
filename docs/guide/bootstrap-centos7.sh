# Configure repositories
yum -y install epel-release
yum -y install https://repos.fedorapeople.org/repos/openstack/openstack-juno/rdo-release-juno-1.noarch.rpm
yum -y install http://opennodecloud.com/centos/7/nodeconductor-release.rpm

# Install and enable services
yum -y install mariadb-server nodeconductor-wsgi redis

systemctl enable httpd
systemctl enable mariadb
systemctl enable nodeconductor-celery
systemctl enable nodeconductor-celerybeat
systemctl enable redis

# Start MySQL and Redis
systemctl start mariadb
systemctl start redis

# Create MySQL database
mysql -e "CREATE DATABASE nodeconductor CHARACTER SET = utf8"
mysql -e "CREATE USER 'nodeconductor'@'localhost' IDENTIFIED BY 'nodeconductor'"
mysql -e "GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'localhost'"

# Init NodeConductor database
nodeconductor migrate --noinput
chown -R nodeconductor:nodeconductor /var/log/nodeconductor

# Start Celery and Apache
systemctl start httpd
curl --head http://localhost/api/
systemctl start nodeconductor-celery
systemctl start nodeconductor-celerybeat
