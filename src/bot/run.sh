. get-bot-image.sh
docker rm -f SCBoardBot 
docker run -d --restart always \
    --name SCBoardBot \
    -v $(pwd)/config.json:/app/bot/config.json \
    sIMAGE_NAME
