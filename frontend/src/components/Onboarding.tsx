/** 첫 방문 안내. 한 번 닫으면 다시 보이지 않는다. */
export default function Onboarding({ onClose }: { onClose: () => void }) {
  return (
    <div className="onboard" role="dialog" aria-labelledby="onboard-title">
      <h2 id="onboard-title" className="onboard__title">교통약자를 위한 길찾기예요</h2>
      <ol className="onboard__steps">
        <li><b>이용자 유형</b>을 고르면 계단·급경사·턱을 피하고 엘리베이터가 있는 길만 찾아요.</li>
        <li>출발지·도착지를 넣거나 <b>현재 위치</b> 버튼으로 바로 시작할 수 있어요.</li>
        <li>추천 경로 3개 중 하나를 고르면 <b>다음부터 취향에 맞게</b> 추천돼요. 지도에서 <b>경사·그늘·시설</b>도 볼 수 있어요.</li>
      </ol>
      <button type="button" className="cta" onClick={onClose}>시작하기</button>
    </div>
  )
}
